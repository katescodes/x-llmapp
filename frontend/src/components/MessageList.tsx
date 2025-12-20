import React from "react";
import { ChatMessage } from "../types";
import MessageBubble from "./MessageBubble";
import { ModularAnswer } from "./ModularAnswer";

interface MessageListProps {
  messages: ChatMessage[];
  messagesEndRef?: React.RefObject<HTMLDivElement>;
}

const MessageList: React.FC<MessageListProps> = ({ messages, messagesEndRef }) => {
  return (
    <>
      {messages.map((msg) => (
        <div
          key={msg.id}
          className={`message-row ${msg.role === "user" ? "user" : "assistant"}`}
        >
          {msg.role === "assistant" && msg.sections && msg.sections.length > 0 ? (
            // 使用模块化渲染（编排器模式）
            <div className="modular-message">
              <ModularAnswer
                sections={msg.sections}
                followups={msg.followups}
              />
            </div>
          ) : (
            // 使用传统气泡渲染
            <MessageBubble role={msg.role} content={msg.content} />
          )}
        </div>
      ))}
      {messages.length === 0 && (
        <div style={{ fontSize: 14, color: "#6b7280", marginTop: 20 }}>
          👋 你好，可以试试问：
          <br />
          "帮我搜索一下最近的量子计算进展"
        </div>
      )}
      <div ref={messagesEndRef} />
    </>
  );
};

export default MessageList;
