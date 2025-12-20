import React, { useState, useRef } from "react";

interface Attachment {
  id: string;
  name: string;
  size: number;
  mime: string;
  status: 'uploading' | 'done' | 'error';
  errorMessage?: string;
}

interface MessageInputProps {
  onSend: (text: string, attachmentIds?: string[]) => void;
  pending: boolean;
  apiBaseUrl?: string;
}

const MessageInput: React.FC<MessageInputProps> = ({ onSend, pending, apiBaseUrl = "" }) => {
  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const tempId = `temp-${Date.now()}-${i}`;
      
      // 添加上传中的附件
      const newAttachment: Attachment = {
        id: tempId,
        name: file.name,
        size: file.size,
        mime: file.type,
        status: 'uploading'
      };
      setAttachments(prev => [...prev, newAttachment]);

      // 上传
      try {
        const formData = new FormData();
        formData.append('file', file);
        
        const resp = await fetch(`${apiBaseUrl}/api/attachments/upload`, {
          method: 'POST',
          body: formData
        });

        if (!resp.ok) {
          const errorData = await resp.json().catch(() => ({ detail: '上传失败' }));
          throw new Error(errorData.detail || '上传失败');
        }

        const data = await resp.json();
        
        // 更新为成功状态
        setAttachments(prev => 
          prev.map(att => 
            att.id === tempId 
              ? { ...att, id: data.id, status: 'done' as const }
              : att
          )
        );
      } catch (error) {
        console.error('文件上传失败:', error);
        // 更新为错误状态
        setAttachments(prev =>
          prev.map(att =>
            att.id === tempId
              ? {
                  ...att,
                  status: 'error' as const,
                  errorMessage: error instanceof Error ? error.message : '上传失败'
                }
              : att
          )
        );
      }
    }

    // 清空文件输入
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleRemoveAttachment = (id: string) => {
    setAttachments(prev => prev.filter(att => att.id !== id));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || pending) return;
    
    // 获取成功上传的附件ID
    const successfulAttachmentIds = attachments
      .filter(att => att.status === 'done')
      .map(att => att.id);
    
    onSend(text.trim(), successfulAttachmentIds.length > 0 ? successfulAttachmentIds : undefined);
    setText("");
    // 注释掉自动清空附件，改为需要用户手动删除
    // setAttachments([]); // 清空附件列表
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e as any);
    }
  };

  const hasUploadingAttachments = attachments.some(att => att.status === 'uploading');

  return (
    <div className="input-container">
      {/* 附件列表 */}
      {attachments.length > 0 && (
        <div className="attachments-list">
          {attachments.map(att => (
            <div key={att.id} className={`attachment-chip ${att.status}`}>
              <span className="attachment-name" title={att.name}>
                {att.name}
              </span>
              <span className="attachment-size">
                ({formatFileSize(att.size)})
              </span>
              {att.status === 'uploading' && (
                <span className="attachment-status">上传中...</span>
              )}
              {att.status === 'error' && (
                <span className="attachment-status error" title={att.errorMessage}>
                  ✗ 失败
                </span>
              )}
              {att.status === 'done' && (
                <span className="attachment-status success">✓</span>
              )}
              <button
                type="button"
                className="attachment-remove"
                onClick={() => handleRemoveAttachment(att.id)}
                disabled={att.status === 'uploading'}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      {/* 输入框 */}
      <form className="input-form" onSubmit={handleSubmit}>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".txt,.md,.pdf,.docx,.pptx,.json,.csv"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />
        <button
          type="button"
          className="btn-attachment"
          onClick={() => fileInputRef.current?.click()}
          disabled={pending || hasUploadingAttachments}
          title="上传附件（支持 .txt .md .pdf .docx .pptx .json .csv）"
        >
          ＋
        </button>
        <textarea
          className="input-textarea"
          placeholder="问我任何问题，支持本地模型 + 联网搜索 + RAG…（Enter 发送，Shift+Enter 换行）"
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button 
          className="btn-primary" 
          type="submit" 
          disabled={pending || hasUploadingAttachments}
        >
          {hasUploadingAttachments ? "上传中…" : pending ? "生成中…" : "发送"}
        </button>
      </form>
    </div>
  );
};

export default MessageInput;
