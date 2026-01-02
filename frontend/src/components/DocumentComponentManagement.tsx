/**
 * 文档组件管理
 * 真正的 Word 风格 - 左侧目录导航 + 右侧统一的连续文档
 */
import React, { useState, useCallback, useRef, useEffect } from 'react';
import { api } from '../config/api';

// ========== 类型定义 ==========

interface DocumentNode {
  id: string;
  parentId: string | null;
  title: string;
  orderNo?: string;
  level: number;
  children?: DocumentNode[];
}

interface DocumentContent {
  nodeId: string;
  html: string;
  status: 'draft' | 'generated' | 'final';
}

// ========== 辅助函数（组件外部）==========

// 将招投标目录格式转换为文档编辑器格式
const convertTenderDirectoryToDocNodes = (tenderNodes: any[]): DocumentNode[] => {
  const result: DocumentNode[] = [];
  const idMap = new Map<string, DocumentNode>();

  // 第一遍：创建所有节点
  tenderNodes.forEach((node, index) => {
    const docNode: DocumentNode = {
      id: node.id || `node-${index}`,
      parentId: null,  // 先设为null，后面建立父子关系
      title: node.title || '',
      orderNo: node.numbering || '',
      level: node.level || 1,
      children: [],
    };
    idMap.set(docNode.id, docNode);
  });

  // 第二遍：建立父子关系（基于level）
  const nodeArray = Array.from(idMap.values());
  const stack: DocumentNode[] = [];
  
  nodeArray.forEach((node) => {
    // 弹出所有level >= 当前node的节点
    while (stack.length > 0 && stack[stack.length - 1].level >= node.level) {
      stack.pop();
    }

    if (stack.length === 0) {
      // 根节点
      result.push(node);
    } else {
      // 子节点
      const parent = stack[stack.length - 1];
      node.parentId = parent.id;
      parent.children = parent.children || [];
      parent.children.push(node);
    }

    stack.push(node);
  });

  return result;
};

// ========== 主组件 ==========

interface DocumentComponentManagementProps {
  embedded?: boolean;  // 是否嵌入到其他组件中
  initialDirectory?: any[];  // 初始目录数据（从招投标/申报书传入）
  projectId?: string;  // 项目ID
  moduleType?: 'tender' | 'declare';  // 模块类型：招投标或申报书
}

export default function DocumentComponentManagement({
  embedded = false,
  initialDirectory,
  projectId,
  moduleType = 'tender',  // 默认为招投标
}: DocumentComponentManagementProps = {}) {
  // -------------------- 状态管理 --------------------
  
  // 示例目录数据（如果没有外部传入，使用示例数据）
  const [directory, setDirectory] = useState<DocumentNode[]>(() => {
    if (initialDirectory && initialDirectory.length > 0) {
      // 将招投标目录转换为文档编辑器格式
      return convertTenderDirectoryToDocNodes(initialDirectory);
    }
    // 默认示例数据
    return [
      {
        id: '1',
        parentId: null,
        title: '第一章 项目概述',
        orderNo: '1',
        level: 1,
        children: [
          { id: '1-1', parentId: '1', title: '项目背景', orderNo: '1.1', level: 2 },
          { id: '1-2', parentId: '1', title: '项目意义', orderNo: '1.2', level: 2 },
        ],
      },
      {
        id: '2',
        parentId: null,
        title: '第二章 技术方案',
        orderNo: '2',
        level: 1,
        children: [
          { id: '2-1', parentId: '2', title: '技术路线', orderNo: '2.1', level: 2 },
          { id: '2-2', parentId: '2', title: '实施计划', orderNo: '2.2', level: 2 },
        ],
      },
    ];
  });

  // 内容数据
  const [contents, setContents] = useState<Record<string, DocumentContent>>({
    '1': {
      nodeId: '1',
      html: '<p><strong>第一章 项目概述</strong></p><p>本章节介绍项目的整体情况，包括项目背景、研究意义等内容...</p>',
      status: 'draft',
    },
    '1-1': {
      nodeId: '1-1',
      html: '<p>随着科技的快速发展，行业面临着诸多挑战。本项目旨在通过创新技术解决这些问题...</p>',
      status: 'draft',
    },
    '1-2': {
      nodeId: '1-2',
      html: '<p>本项目的实施将带来显著的经济效益和社会效益，推动行业的技术进步...</p>',
      status: 'draft',
    },
  });

  // 当前选中的节点（用于高亮）
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>('1');

  // 编辑状态
  const [editingNodeId, setEditingNodeId] = useState<string | null>(null);
  const [editingNodeTitle, setEditingNodeTitle] = useState('');

  // 展开的节点
  const [expandedNodes, setExpandedNodes] = useState<Set<string>>(new Set(['1', '2']));

  // 统一的文档内容（所有章节合并）
  const [unifiedContent, setUnifiedContent] = useState('');

  // 内容编辑器的引用
  const editorRef = useRef<HTMLDivElement | null>(null);

  // 章节标题的引用（用于滚动定位）
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({});

  // 右侧滚动容器的引用
  const rightScrollContainerRef = useRef<HTMLDivElement | null>(null);

  // AI助手对话框（默认收起）
  const [showAIChat, setShowAIChat] = useState(false);
  const [aiChatInput, setAIChatInput] = useState('');
  const [aiChatHistory, setAIChatHistory] = useState<Array<{role: 'user' | 'assistant', content: string}>>([]);
  const [isAIProcessing, setIsAIProcessing] = useState(false);

  // 目录显示/隐藏状态
  const [isDirectoryVisible, setIsDirectoryVisible] = useState(true);

  // -------------------- 合并文档内容 --------------------

  // 将所有章节内容合并成一个 HTML
  useEffect(() => {
    const flatDirectory = flattenDirectory(directory);
    let combinedHtml = '';

    flatDirectory.forEach((node) => {
      const content = contents[node.id];
      const contentHtml = content?.html || '<p style="color: #64748b; font-style: italic;">（暂无内容，点击下方"生成"或直接编辑）</p>';

      // 章节标题（带锚点 ID）
      const headingLevel = Math.min(node.level, 6); // H1-H6
      const headingStyle = `
        font-size: ${24 - node.level * 2}px;
        font-weight: ${node.level === 1 ? 700 : 600};
        color: #f8fafc;
        margin-top: ${node.level === 1 ? 40 : 24}px;
        margin-bottom: 16px;
        padding-bottom: 8px;
        border-bottom: ${node.level === 1 ? '2px solid rgba(148, 163, 184, 0.3)' : 'none'};
      `;

      combinedHtml += `
        <div id="section-${node.id}" style="margin-bottom: 32px;">
          <h${headingLevel} style="${headingStyle}">
            ${node.orderNo ? `<span style="color: #94a3b8; margin-right: 8px;">${node.orderNo}</span>` : ''}
            ${node.title}
          </h${headingLevel}>
          <div style="color: #e5e7eb; line-height: 1.8; font-size: 15px;">
            ${contentHtml}
          </div>
        </div>
      `;
    });

    setUnifiedContent(combinedHtml);
  }, [directory, contents]);

  // -------------------- 目录树操作 --------------------

  // 将目录树展平成列表
  const flattenDirectory = (nodes: DocumentNode[]): DocumentNode[] => {
    const result: DocumentNode[] = [];
    const traverse = (nodeList: DocumentNode[]) => {
      for (const node of nodeList) {
        result.push(node);
        if (node.children && node.children.length > 0) {
          traverse(node.children);
        }
      }
    };
    traverse(nodes);
    return result;
  };

  // 展开/折叠节点
  const toggleNode = (nodeId: string) => {
    setExpandedNodes((prev) => {
      const next = new Set(prev);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  };

  // 选中节点并滚动到对应位置
  const handleSelectNode = (nodeId: string) => {
    // 先获取DOM元素引用
    const targetElement = sectionRefs.current[nodeId];
    const scrollContainer = rightScrollContainerRef.current;
    
    if (targetElement && scrollContainer) {
      // ✅ 在更新状态前先计算滚动位置
      const containerRect = scrollContainer.getBoundingClientRect();
      const targetRect = targetElement.getBoundingClientRect();
      
      // 计算目标元素相对于容器顶部的偏移
      const relativeTop = targetRect.top - containerRect.top;
      
      // 工具栏高度（约80px）+ 一些padding（20px）
      const toolbarHeight = 100;
      
      // 计算需要滚动的距离：当前滚动位置 + 相对偏移 - 工具栏高度
      const scrollTop = scrollContainer.scrollTop + relativeTop - toolbarHeight;
      
      // 平滑滚动到计算的位置
      scrollContainer.scrollTo({
        top: scrollTop,
        behavior: 'smooth',
      });
    }
    
    // ✅ 滚动计算完成后再更新选中状态
    setSelectedNodeId(nodeId);
  };

  // 开始编辑节点标题
  const handleStartEditNode = (node: DocumentNode, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditingNodeId(node.id);
    setEditingNodeTitle(node.title);
  };

  // 保存节点标题
  const handleSaveNodeTitle = () => {
    if (!editingNodeId) return;

    const updateNodeTitle = (nodes: DocumentNode[]): DocumentNode[] => {
      return nodes.map((node) => {
        if (node.id === editingNodeId) {
          return { ...node, title: editingNodeTitle };
        }
        if (node.children) {
          return { ...node, children: updateNodeTitle(node.children) };
        }
        return node;
      });
    };

    setDirectory(updateNodeTitle(directory));
    setEditingNodeId(null);
    setEditingNodeTitle('');
  };

  // 取消编辑
  const handleCancelEdit = () => {
    setEditingNodeId(null);
    setEditingNodeTitle('');
  };

  // 删除节点
  const handleDeleteNode = (nodeId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm('确定要删除此节点吗？')) return;

    const deleteNode = (nodes: DocumentNode[]): DocumentNode[] => {
      return nodes
        .filter((node) => node.id !== nodeId)
        .map((node) => {
          if (node.children) {
            return { ...node, children: deleteNode(node.children) };
          }
          return node;
        });
    };

    setDirectory(deleteNode(directory));

    // 删除对应的内容
    setContents((prev) => {
      const next = { ...prev };
      delete next[nodeId];
      return next;
    });

    // 如果删除的是当前选中的节点，清空选中
    if (selectedNodeId === nodeId) {
      setSelectedNodeId(null);
    }
  };

  // 自动计算编号
  const calculateOrderNo = (parentId: string | null, siblings: DocumentNode[]) => {
    if (parentId === null) {
      // 根节点：计算最大编号 + 1
      const maxNo = siblings.length > 0 
        ? Math.max(...siblings.map(n => parseInt(n.orderNo || '0')))
        : 0;
      return String(maxNo + 1);
    } else {
      // 子节点：父编号 + . + 序号
      const parentNode = findNodeById(directory, parentId);
      if (!parentNode) return '1';
      
      const parentOrderNo = parentNode.orderNo || '1';
      const siblingCount = (parentNode.children || []).length;
      return `${parentOrderNo}.${siblingCount + 1}`;
    }
  };

  // 添加子节点（支持无限层级，自动编号）
  const handleAddChildNode = (parentId: string | null, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();

    const newId = Date.now().toString();
    
    // 计算新节点的层级
    let newLevel = 1;
    let siblings: DocumentNode[] = directory;
    
    if (parentId) {
      const parentNode = findNodeById(directory, parentId);
      if (parentNode) {
        newLevel = parentNode.level + 1;
        siblings = parentNode.children || [];
      }
    }
    
    // 自动计算编号
    const orderNo = calculateOrderNo(parentId, siblings);
    
    const newNode: DocumentNode = {
      id: newId,
      parentId,
      title: '新节点',
      level: newLevel,
      orderNo,
    };

    if (parentId === null) {
      // 添加根节点
      setDirectory([...directory, newNode]);
    } else {
      // 添加子节点（递归）
      const addChild = (nodes: DocumentNode[]): DocumentNode[] => {
        return nodes.map((node) => {
          if (node.id === parentId) {
            return {
              ...node,
              children: [...(node.children || []), newNode],
            };
          }
          if (node.children) {
            return { ...node, children: addChild(node.children) };
          }
          return node;
        });
      };

      setDirectory(addChild(directory));
      // 自动展开父节点
      setExpandedNodes((prev) => new Set([...prev, parentId]));
    }

    // 初始化新节点的内容
    setContents((prev) => ({
      ...prev,
      [newId]: {
        nodeId: newId,
        html: '',
        status: 'draft',
      },
    }));

    // 选中新节点并进入编辑模式
    setSelectedNodeId(newId);
    setEditingNodeId(newId);
    setEditingNodeTitle('新节点');
  };

  // 查找节点（辅助函数）
  const findNodeById = (nodes: DocumentNode[], id: string): DocumentNode | null => {
    for (const node of nodes) {
      if (node.id === id) return node;
      if (node.children) {
        const found = findNodeById(node.children, id);
        if (found) return found;
      }
    }
    return null;
  };

  // -------------------- 内容编辑 --------------------

  // 当编辑器内容改变时（失去焦点时保存），解析并更新各章节内容
  const handleContentChange = () => {
    if (!editorRef.current) return;

    // 遍历所有章节，提取各自的内容
    flattenDirectory(directory).forEach((node) => {
      const sectionElement = sectionRefs.current[node.id];
      if (sectionElement) {
        // 找到该章节的内容部分
        const contentDiv = sectionElement.querySelector('[data-content="true"]') as HTMLElement;
        if (contentDiv) {
          const contentHtml = contentDiv.innerHTML;
          
          // 更新状态（只在失去焦点时更新，避免输入时频繁渲染导致光标跳动）
          setContents((prev) => ({
            ...prev,
            [node.id]: {
              nodeId: node.id,
              html: contentHtml,
              status: 'draft', // 手动编辑的标记为草稿
            },
          }));
        }
      }
    });
  };

  // 内置默认提示词
  const DEFAULT_PROMPT = `请按照申报书的专业标准生成内容：
1. 语言要严谨规范，逻辑清晰
2. 内容要充实具体，有理有据
3. 突出创新点和实用价值
4. 每个章节300-500字
5. 使用专业术语，符合行业规范`;

  // AI助手处理修改请求
  const handleAIChatSubmit = async () => {
    if (!aiChatInput.trim() || isAIProcessing) return;

    const userMessage = aiChatInput.trim();
    setAIChatInput('');
    setIsAIProcessing(true);

    // 添加用户消息到历史
    setAIChatHistory(prev => [...prev, { role: 'user', content: userMessage }]);

    try {
      // 调用后端API，让AI理解用户意图并生成内容
      const flatNodes = flattenDirectory(directory);
      let modified = false;
      let modifiedNodeTitle = '';

      // 如果是嵌入模式且有projectId，调用真实API
      if (embedded && projectId) {
        // 分析用户意图，找到要修改的章节
        for (const node of flatNodes) {
          // 简单的关键词匹配（可以改进为调用AI分析意图的API）
          if (userMessage.includes(node.title) || 
              userMessage.includes(node.orderNo || '') ||
              userMessage.match(/第[一二三四五六七八九十]+章/)) {
            
            try {
              // 调用后端API生成内容（根据模块类型使用不同的API路径）
              const apiPath = moduleType === 'declare' 
                ? `/api/apps/declare/projects/${projectId}/sections/generate`
                : `/api/apps/tender/projects/${projectId}/sections/generate`;
              
              // 使用统一的 api.post 方法，会自动处理认证
              const data = await api.post(apiPath, {
                title: node.title,
                level: node.level,
                requirements: userMessage, // 将用户要求传给后端
              });

              const generatedContent = data.content || '<p>生成失败</p>';

              setContents(prev => ({
                ...prev,
                [node.id]: {
                  nodeId: node.id,
                  html: generatedContent,
                  status: 'generated',
                },
              }));

              modified = true;
              modifiedNodeTitle = node.title;
              
              // 滚动到修改的章节
              setSelectedNodeId(node.id);
              setTimeout(() => {
                handleSelectNode(node.id);  // ✅ 使用统一的滚动方法
              }, 100);

              break;
            } catch (error) {
              console.error('[AI助手] 生成内容失败:', error);
              setAIChatHistory(prev => [...prev, { 
                role: 'assistant', 
                content: `❌ 生成失败：${error}` 
              }]);
              setIsAIProcessing(false);
              return;
            }
          }
        }
      } else {
        // 非嵌入模式，使用模拟数据
        for (const node of flatNodes) {
          if (userMessage.includes(node.title) || 
              userMessage.includes(node.orderNo || '') ||
              userMessage.match(/第[一二三四五六七八九十]+章/)) {
            
            const modifiedContent = `<p><strong>${node.title}</strong></p>
            <p>这是根据您的要求"${userMessage}"生成的示例内容。</p>
            <p>在实际应用中，这里会调用AI模型根据您的要求生成真实的专业内容。</p>`;

            setContents(prev => ({
              ...prev,
              [node.id]: {
                nodeId: node.id,
                html: modifiedContent,
                status: 'generated',
              },
            }));

            modified = true;
            modifiedNodeTitle = node.title;
            setSelectedNodeId(node.id);
            setTimeout(() => {
              handleSelectNode(node.id);  // ✅ 使用统一的滚动方法
            }, 100);

            break;
          }
        }
      }

      // 不再返回确认消息，只在找不到章节时提示
      if (!modified) {
        setAIChatHistory(prev => [...prev, { 
          role: 'assistant', 
          content: '❓ 没有找到对应的章节。请更明确地指出要修改的章节，比如"修改投标函的内容"或"生成第一章"。' 
        }]);
      }

    } catch (error) {
      setAIChatHistory(prev => [...prev, { 
        role: 'assistant', 
        content: `❌ 处理失败：${error}` 
      }]);
    } finally {
      setIsAIProcessing(false);
    }
  };

  // 模拟 AI 生成某个章节的内容
  const handleGenerateContent = async (nodeId: string, requirements?: string) => {
    const node = findNodeById(directory, nodeId);
    if (!node) return;

    console.log('[生成内容] embedded:', embedded, 'projectId:', projectId, 'node:', node);

    // 如果是嵌入模式且有projectId，调用真实的后端API
    if (embedded && projectId) {
      console.log('[生成内容] 调用真实API');
      try {
        // 标记为生成中
        setContents((prev) => ({
          ...prev,
          [nodeId]: {
            nodeId,
            html: '<p style="color: #3b82f6; padding: 20px;">⏳ AI正在生成内容...</p>',
            status: 'draft',
          },
        }));

        // 调用后端API生成内容（根据模块类型使用不同的API路径）
        const apiPath = moduleType === 'declare'
          ? `/api/apps/declare/projects/${projectId}/sections/generate`
          : `/api/apps/tender/projects/${projectId}/sections/generate`;
        
        console.log('[生成内容] API URL:', apiPath);
        
        // 使用统一的 api.post 方法，会自动处理认证
        const data = await api.post(apiPath, {
          title: node.title,
          level: node.level,
          requirements: requirements || undefined,
        });

        console.log('[生成内容] API返回数据:', data);
        const generatedHtml = data.content || '<p>生成失败</p>';

        setContents((prev) => ({
          ...prev,
          [nodeId]: {
            nodeId,
            html: generatedHtml,
            status: 'generated',
          },
        }));
      } catch (error) {
        console.error('[生成内容] 生成失败:', error);
        setContents((prev) => ({
          ...prev,
          [nodeId]: {
            nodeId,
            html: `<p style="color: #ef4444; padding: 20px;">❌ 生成失败：${error}</p>`,
            status: 'draft',
          },
        }));
      }
    } else {
      console.log('[生成内容] 使用模拟数据, embedded=', embedded, 'projectId=', projectId);
      // 独立模式或没有projectId时，使用模拟数据（仅用于演示）
      const mockContent = `<p>这是由 AI 自动生成的<strong>${node.title}</strong>的示例内容。</p>
<p>在实际应用中，这里将调用后端 AI 接口根据章节标题生成相关内容。</p>
<ul>
  <li><strong>要点一：</strong>基于项目背景，阐述关键技术创新点</li>
  <li><strong>要点二：</strong>分析市场需求和应用前景</li>
  <li><strong>要点三：</strong>详细说明具体实施方案和步骤</li>
</ul>
<p>详细内容将根据项目实际情况和申报要求进行生成...</p>`;

      setContents((prev) => ({
        ...prev,
        [nodeId]: {
          nodeId,
          html: mockContent,
          status: 'generated',
        },
      }));
    }
  };

  // 一键生成所有章节内容
  const handleBatchGenerate = async () => {
    setIsAIProcessing(true);
    const flatNodes = flattenDirectory(directory);
    
    try {
      // ✅ 串行生成：等待每个章节生成完成后再生成下一个
      for (let i = 0; i < flatNodes.length; i++) {
        const node = flatNodes[i];
        
        // 添加短暂延迟，避免请求过快
        if (i > 0) {
          await new Promise(resolve => setTimeout(resolve, 500));
        }
        
        // ✅ 关键：使用await等待每个章节生成完成
        await handleGenerateContent(node.id, undefined);
      }
      
      alert(`✅ 成功生成 ${flatNodes.length} 个章节的内容！`);
    } catch (error) {
      console.error('[一键生成] 批量生成失败:', error);
      alert('❌ 批量生成失败：' + error);
    } finally {
      setIsAIProcessing(false);
    }
  };

  // -------------------- 渲染目录树 --------------------

  const renderNode = (node: DocumentNode) => {
    const isSelected = selectedNodeId === node.id;
    const isExpanded = expandedNodes.has(node.id);
    const hasChildren = node.children && node.children.length > 0;
    const isEditing = editingNodeId === node.id;

    return (
      <div key={node.id} style={{ marginLeft: node.level === 1 ? 0 : 20 }}>
        <div
          onClick={() => handleSelectNode(node.id)}
          style={{
            padding: '8px 12px',
            background: isSelected ? 'rgba(79, 70, 229, 0.15)' : 'transparent',
            borderLeft: isSelected ? '3px solid #818cf8' : '3px solid transparent',
            cursor: 'pointer',
            borderRadius: 4,
            marginBottom: 4,
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => {
            if (!isSelected) {
              e.currentTarget.style.background = 'rgba(148, 163, 184, 0.05)';
            }
          }}
          onMouseLeave={(e) => {
            if (!isSelected) {
              e.currentTarget.style.background = 'transparent';
            }
          }}
        >
          {/* 展开/折叠图标 */}
          {hasChildren && (
            <span
              onClick={(e) => {
                e.stopPropagation();
                toggleNode(node.id);
              }}
              style={{ cursor: 'pointer', userSelect: 'none', width: 16 }}
            >
              {isExpanded ? '▼' : '▶'}
            </span>
          )}
          {!hasChildren && <span style={{ width: 16 }} />}

          {/* 节点标题 */}
          {isEditing ? (
            <input
              type="text"
              value={editingNodeTitle}
              onChange={(e) => setEditingNodeTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSaveNodeTitle();
                if (e.key === 'Escape') handleCancelEdit();
              }}
              onBlur={handleSaveNodeTitle}
              autoFocus
              onClick={(e) => e.stopPropagation()}
              style={{
                flex: 1,
                padding: '4px 8px',
                border: '1px solid #818cf8',
                borderRadius: 4,
                background: 'rgba(15, 23, 42, 0.8)',
                color: '#e5e7eb',
                fontSize: 14,
              }}
            />
          ) : (
            <span 
              style={{ 
                flex: 1, 
                color: '#e5e7eb', 
                fontSize: 14,
                overflow: 'hidden',  // ✅ 隐藏溢出
                textOverflow: 'ellipsis',  // ✅ 显示省略号
                whiteSpace: 'nowrap',  // ✅ 不换行
              }}
              title={`${node.orderNo ? node.orderNo + ' ' : ''}${node.title}`}  // ✅ hover显示完整标题
            >
              {node.orderNo && <span style={{ color: '#94a3b8', marginRight: 4 }}>{node.orderNo}</span>}
              {node.title}
            </span>
          )}

          {/* 操作按钮（鼠标悬停时显示） */}
          {!isEditing && (
            <div style={{ display: 'flex', gap: 4, opacity: isSelected ? 1 : 0 }}>
              <button
                onClick={(e) => handleStartEditNode(node, e)}
                title="编辑"
                style={{
                  padding: '2px 6px',
                  border: 'none',
                  background: 'rgba(79, 70, 229, 0.2)',
                  color: '#818cf8',
                  borderRadius: 3,
                  cursor: 'pointer',
                  fontSize: 12,
                }}
              >
                ✏️
              </button>
              <button
                onClick={(e) => handleAddChildNode(node.id, e)}
                title="添加下级"
                style={{
                  padding: '2px 6px',
                  border: 'none',
                  background: 'rgba(34, 197, 94, 0.2)',
                  color: '#22c55e',
                  borderRadius: 3,
                  cursor: 'pointer',
                  fontSize: 12,
                }}
              >
                ➕
              </button>
              <button
                onClick={(e) => handleDeleteNode(node.id, e)}
                title="删除"
                style={{
                  padding: '2px 6px',
                  border: 'none',
                  background: 'rgba(239, 68, 68, 0.2)',
                  color: '#ef4444',
                  borderRadius: 3,
                  cursor: 'pointer',
                  fontSize: 12,
                }}
              >
                🗑️
              </button>
            </div>
          )}
        </div>

        {/* 递归渲染子节点 */}
        {hasChildren && isExpanded && (
          <div style={{ marginTop: 4 }}>
            {node.children!.map((child) => renderNode(child))}
          </div>
        )}
      </div>
    );
  };

  // -------------------- 主界面 --------------------

  const flatDirectory = flattenDirectory(directory);

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
        color: '#f8fafc',
        minHeight: embedded ? '100%' : '100vh',      // ✅ 最小高度
        height: embedded ? '100%' : 'auto',          // ✅ 嵌入模式填满容器
        position: embedded ? 'absolute' : 'relative', // ✅ 嵌入模式绝对定位
        top: embedded ? 0 : 'auto',
        left: embedded ? 0 : 'auto',
        right: embedded ? 0 : 'auto',
        bottom: embedded ? 0 : 'auto',
      }}
    >
      {/* 标题栏（只在非嵌入模式显示） */}
      {!embedded && (
        <div
          style={{
            padding: '20px 32px',
            borderBottom: '1px solid rgba(148, 163, 184, 0.2)',
          }}
        >
          <h1
            style={{
              margin: 0,
              fontSize: '24px',
              fontWeight: 600,
              color: '#f8fafc',
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
            }}
          >
            <span>📝</span>
            <span>文档组件管理</span>
          </h1>
          <p
            style={{
              margin: '8px 0 0 0',
              fontSize: '14px',
              color: '#94a3b8',
            }}
          >
            Word 风格文档编辑器 - 左侧目录导航 + 右侧统一连续文档
          </p>
        </div>
      )}

      {/* 主内容区 - 左右分栏 */}
      <div style={{ 
        flex: 1, 
        display: 'flex', 
        position: 'relative',
        overflow: 'hidden',  // ✅ 防止溢出，强制内部滚动
      }}>
        {/* 左侧：目录树（sticky定位，不随滚动） */}
        <div
          style={{
            position: 'sticky',  // ✅ sticky定位，不随页面滚动
            left: 0,
            top: 0,
            alignSelf: 'flex-start',
            width: isDirectoryVisible ? '320px' : '0',
            height: '100vh',  // ✅ 固定高度
            background: 'rgba(15, 23, 42, 0.95)',
            backdropFilter: 'blur(10px)',
            borderRight: isDirectoryVisible ? '1px solid rgba(148, 163, 184, 0.2)' : 'none',
            display: 'flex',
            flexDirection: 'column',
            transition: 'width 0.3s ease, opacity 0.3s ease',
            overflow: 'hidden',
            zIndex: 1000,
            opacity: isDirectoryVisible ? 1 : 0,
            boxShadow: isDirectoryVisible ? '4px 0 12px rgba(0, 0, 0, 0.3)' : 'none',
          }}
        >
          {/* 目录工具栏 */}
          <div
            style={{
              padding: '16px',
              borderBottom: '1px solid rgba(148, 163, 184, 0.2)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              flexShrink: 0,
            }}
          >
            <span style={{ fontSize: 16, fontWeight: 600, color: '#e5e7eb', whiteSpace: 'nowrap' }}>📁 目录结构</span>
            <button
              onClick={(e) => handleAddChildNode(null, e)}
              style={{
                padding: '6px 12px',
                border: 'none',
                background: 'rgba(79, 70, 229, 0.2)',
                color: '#818cf8',
                borderRadius: 6,
                cursor: 'pointer',
                fontSize: 13,
                fontWeight: 500,
                whiteSpace: 'nowrap',
              }}
            >
              ➕ 新增章节
            </button>
          </div>

          {/* 目录树 */}
          <div style={{ 
            flex: 1,
            padding: '16px' 
          }}>
            {directory.length === 0 ? (
              <div style={{ textAlign: 'center', color: '#64748b', padding: 40 }}>
                暂无目录，点击"新增章节"开始创建
              </div>
            ) : (
              directory.map((node) => renderNode(node))
            )}
          </div>
        </div>

        {/* 折叠/展开按钮（放在目录和正文之间的顶部） */}
        <button
          onClick={() => setIsDirectoryVisible(!isDirectoryVisible)}
          style={{
            position: 'sticky',  // ✅ sticky定位，不随滚动
            left: isDirectoryVisible ? '320px' : '0',
            top: '0',  // ✅ 顶部对齐
            alignSelf: 'flex-start',
            width: '32px',
            height: '48px',  // ✅ 调整高度适合顶部
            border: '1px solid rgba(148, 163, 184, 0.2)',
            borderLeft: isDirectoryVisible ? 'none' : '1px solid rgba(148, 163, 184, 0.2)',
            borderTop: 'none',  // ✅ 顶部无边框，贴合顶部
            borderRadius: isDirectoryVisible ? '0 0 8px 0' : '0 0 8px 0',  // ✅ 只有底部圆角
            background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
            color: '#94a3b8',
            cursor: 'pointer',
            fontSize: '16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1001,
            transition: 'all 0.3s ease',
            boxShadow: '0 2px 12px rgba(0, 0, 0, 0.4)',
            flexShrink: 0,
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'linear-gradient(135deg, #2d3748 0%, #1a202c 100%)';
            e.currentTarget.style.color = '#e2e8f0';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)';
            e.currentTarget.style.color = '#94a3b8';
          }}
          title={isDirectoryVisible ? '隐藏目录' : '展开目录'}
        >
          {isDirectoryVisible ? '◀' : '▶'}
        </button>

        {/* 右侧：统一的连续文档（全宽） */}
        <div
          ref={rightScrollContainerRef}  // ✅ 添加ref引用
          style={{
            flex: 1,
            display: 'flex',
            flexDirection: 'column',
            width: '100%',
            overflow: 'auto',  // ✅ 右侧整体可滚动
          }}
        >
          {/* 工具栏（sticky固定在顶部） */}
          <div
            style={{
              position: 'sticky',  // ✅ sticky定位，固定在顶部
              top: 0,              // ✅ 贴顶
              zIndex: 100,         // ✅ 高层级
              padding: '16px 24px',
              borderBottom: '1px solid rgba(148, 163, 184, 0.2)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              background: 'rgba(15, 23, 42, 0.95)',  // ✅ 提高不透明度
              backdropFilter: 'blur(10px)',           // ✅ 毛玻璃效果
              flexShrink: 0,
            }}
          >
            <div>
              <h2 style={{ margin: 0, fontSize: 18, color: '#f8fafc' }}>
                📄 文档内容
              </h2>
              <p style={{ margin: '4px 0 0 0', fontSize: 13, color: '#64748b' }}>
                点击左侧目录快速定位 · 所有章节在一个连续的文档中
              </p>
            </div>

            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={() => setShowAIChat(!showAIChat)}
                style={{
                  padding: '8px 16px',
                  border: 'none',
                  background: showAIChat 
                    ? 'linear-gradient(135deg, #8b5cf6, #6366f1)'
                    : 'rgba(139, 92, 246, 0.2)',
                  color: '#fff',
                  borderRadius: 6,
                  cursor: 'pointer',
                  fontSize: 14,
                  fontWeight: 500,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                💬 AI助手 {aiChatHistory.length > 0 && `(${aiChatHistory.length / 2})`}
              </button>
              <button
                onClick={handleBatchGenerate}
                disabled={isAIProcessing || flatDirectory.length === 0}
                style={{
                  padding: '8px 16px',
                  border: 'none',
                  background: isAIProcessing 
                    ? 'rgba(100, 116, 139, 0.5)' 
                    : 'rgba(34, 197, 94, 0.2)',
                  color: isAIProcessing ? '#94a3b8' : '#22c55e',
                  borderRadius: 6,
                  cursor: isAIProcessing || flatDirectory.length === 0 ? 'not-allowed' : 'pointer',
                  fontSize: 14,
                  fontWeight: 500,
                  opacity: isAIProcessing || flatDirectory.length === 0 ? 0.6 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                }}
              >
                {isAIProcessing ? '⏳ 生成中...' : '🚀 一键生成全部'}
              </button>
              <button
                style={{
                  padding: '8px 16px',
                  border: '1px solid rgba(148, 163, 184, 0.3)',
                  background: 'transparent',
                  color: '#94a3b8',
                  borderRadius: 6,
                  cursor: 'pointer',
                  fontSize: 14,
                }}
              >
                💾 保存
              </button>
              <button
                style={{
                  padding: '8px 16px',
                  border: '1px solid rgba(148, 163, 184, 0.3)',
                  background: 'transparent',
                  color: '#94a3b8',
                  borderRadius: 6,
                  cursor: 'pointer',
                  fontSize: 14,
                }}
              >
                📥 导出
              </button>
            </div>
          </div>

          {/* 文档内容区域（连续的、可编辑的，类似Word） */}
          <div
            style={{
              flex: 1,
              padding: '20px',
              background: '#f8f9fa',
            }}
          >
            {flatDirectory.length === 0 ? (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  minHeight: 400,
                  color: '#94a3b8',
                }}
              >
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 48, marginBottom: 16 }}>📝</div>
                  <div style={{ fontSize: 18, color: '#64748b' }}>暂无内容</div>
                  <div style={{ fontSize: 14, marginTop: 8, color: '#94a3b8' }}>
                    点击左侧"新增章节"开始创建文档
                  </div>
                </div>
              </div>
            ) : (
              // Word风格的文档容器
              <div
                style={{
                  width: '100%',
                  minHeight: '29.7cm',
                  background: '#fff',
                  boxShadow: '0 0 10px rgba(0,0,0,0.1)',
                  padding: '2.54cm 3.17cm',
                }}
              >
                <div
                  ref={editorRef}
                  contentEditable={true}
                  onBlur={handleContentChange}
                  suppressContentEditableWarning={true}
                  style={{
                    width: '100%',
                    color: '#1e293b',
                    fontSize: 15,
                    lineHeight: 1.8,
                    outline: 'none',
                    cursor: 'text',
                  }}
                >
                {/* 渲染所有章节的内容（连续的） */}
                {flatDirectory.map((node) => {
                  const content = contents[node.id];
                  const contentHtml = content?.html || '';
                  const hasContent = contentHtml.trim().length > 0;

                  return (
                    <div
                      key={node.id}
                      ref={(el) => {
                        sectionRefs.current[node.id] = el;
                      }}
                      style={{
                        marginBottom: 40,
                        scrollMarginTop: 80,
                      }}
                    >
                      {/* 章节标题 */}
                      <div
                        style={{
                          fontSize: Math.max(24 - node.level * 2, 16),
                          fontWeight: node.level === 1 ? 700 : 600,
                          color: '#0f172a',
                          marginTop: node.level === 1 ? 40 : 24,
                          marginBottom: 16,
                          paddingBottom: 12,
                          borderBottom: node.level === 1 ? '3px solid #e2e8f0' : 'none',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                        }}
                      >
                        <span>
                          {node.orderNo && (
                            <span style={{ color: '#64748b', marginRight: 8 }}>{node.orderNo}</span>
                          )}
                          {node.title}
                        </span>
                        
                        {/* 快捷操作按钮 */}
                        <button
                          onClick={() => handleGenerateContent(node.id)}
                          style={{
                            padding: '6px 12px',
                            border: 'none',
                            background: hasContent 
                              ? 'rgba(100, 116, 139, 0.8)' 
                              : 'linear-gradient(135deg, #8b5cf6, #6366f1)',
                            color: '#fff',
                            borderRadius: 6,
                            cursor: 'pointer',
                            fontSize: 13,
                          }}
                        >
                          {hasContent ? '🔄 重新生成' : '🤖 生成内容'}
                        </button>
                      </div>

                      {/* 章节内容（可编辑） */}
                      <div
                        data-content="true"
                        style={{
                          color: '#334155',
                          fontSize: 15,
                          lineHeight: 1.8,
                        }}
                        dangerouslySetInnerHTML={{
                          __html: hasContent
                            ? contentHtml
                            : '<p style="color: #94a3b8; font-style: italic; padding: 20px; background: #f8fafc; border-radius: 8px;">（暂无内容，点击上方"生成内容"按钮使用 AI 生成，或直接在此处输入内容）</p>',
                        }}
                      />
                    </div>
                  );
                })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>


      {/* AI助手对话框（浮动在右下角） */}
      {showAIChat && (
        <div
          style={{
            position: 'fixed',
            right: 32,
            bottom: 32,
            width: 420,
            height: 600,
            background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
            borderRadius: 16,
            boxShadow: '0 20px 60px rgba(0, 0, 0, 0.5)',
            border: '1px solid rgba(148, 163, 184, 0.3)',
            display: 'flex',
            flexDirection: 'column',
            zIndex: 3000,
          }}
        >
          {/* 头部 */}
          <div
            style={{
              padding: '16px 20px',
              borderBottom: '1px solid rgba(148, 163, 184, 0.2)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 20 }}>💬</span>
              <h3 style={{ margin: 0, fontSize: 16, color: '#f8fafc' }}>AI助手</h3>
            </div>
            <button
              onClick={() => setShowAIChat(false)}
              style={{
                padding: '4px 8px',
                border: 'none',
                background: 'transparent',
                color: '#94a3b8',
                cursor: 'pointer',
                fontSize: 18,
              }}
            >
              ✕
            </button>
          </div>

          {/* 对话历史 */}
          <div
            style={{
              flex: 1,
              overflow: 'auto',
              padding: '16px',
              display: 'flex',
              flexDirection: 'column',
              gap: 12,
            }}
          >
            {aiChatHistory.length === 0 ? (
              <div style={{ textAlign: 'center', color: '#64748b', padding: '40px 20px' }}>
                <div style={{ fontSize: 48, marginBottom: 16 }}>🤖</div>
                <p style={{ fontSize: 15, marginBottom: 8 }}>你好！我是AI助手</p>
                <p style={{ fontSize: 13, color: '#475569' }}>
                  告诉我您想修改文档的哪些地方，比如：
                </p>
                <ul style={{ textAlign: 'left', fontSize: 13, color: '#475569', marginTop: 12 }}>
                  <li>第一章写得太简单，扩展一下</li>
                  <li>技术方案部分增加创新点说明</li>
                  <li>把项目背景改得更专业一些</li>
                </ul>
              </div>
            ) : (
              aiChatHistory.map((msg, index) => (
                <div
                  key={index}
                  style={{
                    alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
                    maxWidth: '80%',
                  }}
                >
                  <div
                    style={{
                      padding: '10px 14px',
                      borderRadius: 12,
                      background: msg.role === 'user'
                        ? 'linear-gradient(135deg, #8b5cf6, #6366f1)'
                        : 'rgba(71, 85, 105, 0.5)',
                      color: '#f8fafc',
                      fontSize: 14,
                      lineHeight: 1.5,
                    }}
                  >
                    {msg.content}
                  </div>
                  <div
                    style={{
                      fontSize: 11,
                      color: '#64748b',
                      marginTop: 4,
                      textAlign: msg.role === 'user' ? 'right' : 'left',
                    }}
                  >
                    {msg.role === 'user' ? '你' : 'AI'}
                  </div>
                </div>
              ))
            )}
            
            {isAIProcessing && (
              <div style={{ alignSelf: 'flex-start', maxWidth: '80%' }}>
                <div
                  style={{
                    padding: '10px 14px',
                    borderRadius: 12,
                    background: 'rgba(71, 85, 105, 0.5)',
                    color: '#94a3b8',
                    fontSize: 14,
                  }}
                >
                  <span className="loading-dots">AI正在思考</span>
                </div>
              </div>
            )}
          </div>

          {/* 输入框 */}
          <div
            style={{
              padding: '12px 16px',
              borderTop: '1px solid rgba(148, 163, 184, 0.2)',
              display: 'flex',
              gap: 8,
            }}
          >
            <input
              type="text"
              value={aiChatInput}
              onChange={(e) => setAIChatInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleAIChatSubmit();
                }
              }}
              placeholder="输入修改要求..."
              disabled={isAIProcessing}
              style={{
                flex: 1,
                padding: '10px 12px',
                border: '1px solid rgba(148, 163, 184, 0.3)',
                borderRadius: 8,
                background: 'rgba(15, 23, 42, 0.8)',
                color: '#e5e7eb',
                fontSize: 14,
              }}
            />
            <button
              onClick={handleAIChatSubmit}
              disabled={!aiChatInput.trim() || isAIProcessing}
              style={{
                padding: '10px 16px',
                border: 'none',
                background: !aiChatInput.trim() || isAIProcessing
                  ? 'rgba(100, 116, 139, 0.5)'
                  : 'linear-gradient(135deg, #8b5cf6, #6366f1)',
                color: '#fff',
                borderRadius: 8,
                cursor: !aiChatInput.trim() || isAIProcessing ? 'not-allowed' : 'pointer',
                fontSize: 14,
                fontWeight: 500,
              }}
            >
              发送
            </button>
          </div>
        </div>
      )}

      {/* 加载动画样式 */}
      <style>{`
        @keyframes loading-dots {
          0%, 20% { content: '.'; }
          40% { content: '..'; }
          60%, 100% { content: '...'; }
        }
        .loading-dots::after {
          content: '...';
          animation: loading-dots 1.5s infinite;
        }
      `}</style>
    </div>
  );
}
