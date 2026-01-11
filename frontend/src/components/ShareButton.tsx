import React, { useState } from 'react';
import { api } from '../config/api';

interface ShareButtonProps {
  resourceType: 'kb' | 'template' | 'rule-pack' | 'document';
  resourceId: string;
  resourceName: string;
  isShared: boolean;
  onShareChange?: (isShared: boolean) => void;
}

const ShareButton: React.FC<ShareButtonProps> = ({
  resourceType,
  resourceId,
  resourceName,
  isShared,
  onShareChange
}) => {
  const [loading, setLoading] = useState(false);
  const [shared, setShared] = useState(isShared);

  const getApiPath = () => {
    switch (resourceType) {
      case 'kb':
        return `/api/kb/${resourceId}`;
      case 'template':
        return `/api/apps/tender/format-templates/${resourceId}`;
      case 'rule-pack':
        return `/api/custom-rules/rule-packs/${resourceId}`;
      case 'document':
        return `/api/user-documents/documents/${resourceId}`;
    }
  };

  const handleToggleShare = async (e: React.MouseEvent) => {
    e.stopPropagation(); // 防止触发父元素的点击事件
    
    if (loading) return;
    
    const action = shared ? 'unshare' : 'share';
    const confirmMsg = shared 
      ? `确定要取消共享"${resourceName}"吗？取消后，企业内其他成员将无法访问。`
      : `确定要共享"${resourceName}"到企业吗？共享后，企业内所有成员都可以访问。`;
    
    if (!confirm(confirmMsg)) return;
    
    setLoading(true);
    try {
      await api.post(`${getApiPath()}/${action}`, {});
      setShared(!shared);
      onShareChange?.(!shared);
      alert(shared ? '取消共享成功' : '共享成功');
    } catch (error: any) {
      console.error('共享操作失败:', error);
      alert(`操作失败: ${error.response?.data?.detail || error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      onClick={handleToggleShare}
      disabled={loading}
      className={`share-btn ${shared ? 'shared' : 'private'}`}
      title={shared ? '点击取消共享' : '点击共享到企业'}
      style={{
        padding: '4px 8px',
        fontSize: '12px',
        borderRadius: '4px',
        border: 'none',
        cursor: loading ? 'not-allowed' : 'pointer',
        background: shared ? '#28a745' : '#6c757d',
        color: 'white',
        opacity: loading ? 0.6 : 1,
        transition: 'all 0.2s'
      }}
    >
      {loading ? '...' : (shared ? '🏢 已共享' : '🔒 私有')}
    </button>
  );
};

export default ShareButton;
