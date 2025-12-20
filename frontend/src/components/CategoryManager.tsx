import React, { useState, useEffect, useCallback } from "react";
import { KbCategory } from "../types";
import { API_BASE_URL } from "../config/api";

interface CategoryManagerProps {
  onClose: () => void;
  onCategoryChanged: () => void;
}

const CategoryManager: React.FC<CategoryManagerProps> = ({ onClose, onCategoryChanged }) => {
  const apiBaseUrl = API_BASE_URL;
  const [categories, setCategories] = useState<KbCategory[]>([]);
  const [loading, setLoading] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [newCategory, setNewCategory] = useState({
    name: "",
    display_name: "",
    color: "#6b7280",
    icon: "📁",
    description: ""
  });

  const fetchCategories = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await fetch(`${apiBaseUrl}/api/kb-categories`);
      if (!resp.ok) throw new Error("获取分类列表失败");
      const data: KbCategory[] = await resp.json();
      setCategories(data);
    } catch (error) {
      console.error(error);
      alert("加载分类列表失败");
    } finally {
      setLoading(false);
    }
  }, [apiBaseUrl]);

  useEffect(() => {
    fetchCategories();
  }, [fetchCategories]);

  const handleCreate = async () => {
    if (!newCategory.name || !newCategory.display_name) {
      alert("请填写分类标识和显示名称");
      return;
    }

    try {
      const resp = await fetch(`${apiBaseUrl}/api/kb-categories`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(newCategory)
      });
      if (!resp.ok) {
        const error = await resp.json();
        throw new Error(error.detail || "创建失败");
      }
      setNewCategory({
        name: "",
        display_name: "",
        color: "#6b7280",
        icon: "📁",
        description: ""
      });
      await fetchCategories();
      onCategoryChanged();
      alert("创建成功");
    } catch (error: any) {
      alert(error.message || "创建分类失败");
    }
  };

  const handleUpdate = async (categoryId: string, updates: Partial<KbCategory>) => {
    try {
      const resp = await fetch(`${apiBaseUrl}/api/kb-categories/${categoryId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(updates)
      });
      if (!resp.ok) throw new Error("更新失败");
      await fetchCategories();
      setEditingId(null);
      onCategoryChanged();
      alert("更新成功");
    } catch (error) {
      alert("更新分类失败");
    }
  };

  const handleDelete = async (categoryId: string) => {
    if (!window.confirm("确认删除该分类？使用该分类的知识库将变为无分类。")) return;

    try {
      const resp = await fetch(`${apiBaseUrl}/api/kb-categories/${categoryId}`, {
        method: "DELETE"
      });
      if (!resp.ok) throw new Error("删除失败");
      await fetchCategories();
      onCategoryChanged();
      alert("删除成功");
    } catch (error) {
      alert("删除分类失败");
    }
  };

  const presetColors = [
    "#10b981", "#3b82f6", "#8b5cf6", "#f59e0b", 
    "#ef4444", "#ec4899", "#14b8a6", "#6366f1"
  ];

  const presetIcons = ["📁", "📚", "📘", "📋", "💡", "🎯", "⭐", "🔥", "✨", "🎨"];

  return (
    <div style={{
      position: "fixed",
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: "rgba(0, 0, 0, 0.7)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      zIndex: 1000
    }}>
      <div style={{
        background: "#1f2937",
        borderRadius: "12px",
        padding: "24px",
        maxWidth: "700px",
        width: "90%",
        maxHeight: "80vh",
        overflow: "auto",
        border: "1px solid #374151"
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "20px" }}>
          <h2 style={{ margin: 0 }}>分类管理</h2>
          <button onClick={onClose} style={{
            background: "transparent",
            border: "none",
            color: "#9ca3af",
            fontSize: "24px",
            cursor: "pointer"
          }}>×</button>
        </div>

        {/* 创建新分类 */}
        <div style={{
          background: "#111827",
          borderRadius: "8px",
          padding: "16px",
          marginBottom: "20px"
        }}>
          <h3>新建分类</h3>
          <div style={{ display: "grid", gap: "12px" }}>
            <input
              type="text"
              placeholder="分类标识（英文，如: knowledge）"
              value={newCategory.name}
              onChange={(e) => setNewCategory({ ...newCategory, name: e.target.value })}
              style={{
                padding: "8px",
                borderRadius: "6px",
                border: "1px solid #374151",
                background: "#0f172a",
                color: "#e5e7eb"
              }}
            />
            <input
              type="text"
              placeholder="显示名称（中文，如: 知识库）"
              value={newCategory.display_name}
              onChange={(e) => setNewCategory({ ...newCategory, display_name: e.target.value })}
              style={{
                padding: "8px",
                borderRadius: "6px",
                border: "1px solid #374151",
                background: "#0f172a",
                color: "#e5e7eb"
              }}
            />
            <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
              <label style={{ fontSize: "14px" }}>颜色：</label>
              <input
                type="color"
                value={newCategory.color}
                onChange={(e) => setNewCategory({ ...newCategory, color: e.target.value })}
                style={{ width: "50px", height: "30px", cursor: "pointer" }}
              />
              <div style={{ display: "flex", gap: "4px" }}>
                {presetColors.map(color => (
                  <button
                    key={color}
                    onClick={() => setNewCategory({ ...newCategory, color })}
                    style={{
                      width: "24px",
                      height: "24px",
                      borderRadius: "4px",
                      background: color,
                      border: newCategory.color === color ? "2px solid white" : "1px solid #374151",
                      cursor: "pointer"
                    }}
                  />
                ))}
              </div>
            </div>
            <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
              <label style={{ fontSize: "14px" }}>图标：</label>
              <div style={{ display: "flex", gap: "4px", flexWrap: "wrap" }}>
                {presetIcons.map(icon => (
                  <button
                    key={icon}
                    onClick={() => setNewCategory({ ...newCategory, icon })}
                    style={{
                      padding: "4px 8px",
                      borderRadius: "4px",
                      background: newCategory.icon === icon ? "#3b82f6" : "#374151",
                      border: "none",
                      cursor: "pointer",
                      fontSize: "18px"
                    }}
                  >
                    {icon}
                  </button>
                ))}
              </div>
            </div>
            <textarea
              placeholder="描述（可选）"
              value={newCategory.description}
              onChange={(e) => setNewCategory({ ...newCategory, description: e.target.value })}
              style={{
                padding: "8px",
                borderRadius: "6px",
                border: "1px solid #374151",
                background: "#0f172a",
                color: "#e5e7eb",
                resize: "vertical",
                minHeight: "60px"
              }}
            />
            <button
              onClick={handleCreate}
              style={{
                padding: "8px 16px",
                borderRadius: "6px",
                background: "linear-gradient(135deg, #4f46e5, #22c55e)",
                border: "none",
                color: "white",
                cursor: "pointer",
                fontWeight: "500"
              }}
            >
              创建分类
            </button>
          </div>
        </div>

        {/* 现有分类列表 */}
        <div>
          <h3>现有分类</h3>
          {loading && <div style={{ color: "#9ca3af" }}>加载中...</div>}
          {!loading && categories.length === 0 && <div style={{ color: "#9ca3af" }}>暂无分类</div>}
          <div style={{ display: "grid", gap: "12px" }}>
            {categories.map(cat => (
              <div key={cat.id} style={{
                background: "#111827",
                borderRadius: "8px",
                padding: "12px",
                border: "1px solid #374151"
              }}>
                {editingId === cat.id ? (
                  <div>编辑功能开发中...</div>
                ) : (
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                      <span style={{ fontSize: "24px" }}>{cat.icon}</span>
                      <div>
                        <div style={{
                          fontWeight: "600",
                          color: cat.color
                        }}>{cat.display_name}</div>
                        <div style={{ fontSize: "12px", color: "#9ca3af" }}>
                          标识: {cat.name}
                        </div>
                        {cat.description && (
                          <div style={{ fontSize: "12px", color: "#9ca3af", marginTop: "4px" }}>
                            {cat.description}
                          </div>
                        )}
                      </div>
                    </div>
                    <div style={{ display: "flex", gap: "8px" }}>
                      <button
                        onClick={() => handleDelete(cat.id)}
                        style={{
                          padding: "4px 12px",
                          borderRadius: "4px",
                          background: "#ef4444",
                          border: "none",
                          color: "white",
                          cursor: "pointer",
                          fontSize: "12px"
                        }}
                      >
                        删除
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

export default CategoryManager;

