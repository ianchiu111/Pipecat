
/*
前端主畫面，用來放置 RTC 的 UI 元件以及接收 Agent 傳來 Data Channel 訊息的地方
*/

"use client";

import { useEffect, useState } from 'react';
import '@livekit/components-styles';
import {
  LiveKitRoom,
  VideoConference,
  RoomAudioRenderer,
  useDataChannel
} from '@livekit/components-react';

export default function MeetingPage() {
  const [token, setToken] = useState('');
  const [isStarted, setIsStarted] = useState(false);
  const [isHovered, setIsHovered] = useState(false);

  // 新增狀態：讓使用者自訂姓名與房間名稱
  const [userName, setUserName] = useState('');
  const [roomName, setRoomName] = useState('default-room'); // 預設給一個房間名

  const handleJoin = async () => {
    // 防呆：確保名字和房間都有填寫
    if (!userName.trim() || !roomName.trim()) return;

    // 將使用者輸入的值帶入 API URL 中
    const res = await fetch(`/api/token?room=${encodeURIComponent(roomName)}&username=${encodeURIComponent(userName)}`);
    const data = await res.json();
    
    if (data.token) {
      setToken(data.token);
      setIsStarted(true);
    } else {
      alert("獲取憑證失敗，請檢查網路狀態");
    }
  };

  // 檢查是否可以點擊按鈕
  const isFormValid = userName.trim() !== '' && roomName.trim() !== '';

  if (!isStarted) {
    return (
      <div style={{ 
        display: 'flex', 
        flexDirection: 'column',
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '100vh',
        backgroundColor: '#f8f9fa',
        fontFamily: 'sans-serif'
      }}>
        <h1 style={{ color: '#333', marginBottom: '10px', fontSize: '2rem' }}>
          線上即時會議
        </h1>
        <p style={{ color: '#666', marginBottom: '30px', fontSize: '1.1rem' }}>
          請輸入您的稱呼與會議室名稱，以開始會議
        </p>

        {/* 新增：使用者姓名輸入框 */}
        <input 
          type="text" 
          placeholder="您的稱呼 (例: 王先生)" 
          value={userName}
          onChange={(e) => setUserName(e.target.value)}
          style={{
            padding: '12px 16px',
            marginBottom: '15px',
            width: '280px',
            borderRadius: '8px',
            border: '1px solid #ccc',
            fontSize: '1rem',
            outline: 'none',
          }}
        />

        {/* 新增：房間名稱輸入框 */}
        <input 
          type="text" 
          placeholder="會議室名稱" 
          value={roomName}
          onChange={(e) => setRoomName(e.target.value)}
          style={{
            padding: '12px 16px',
            marginBottom: '30px',
            width: '280px',
            borderRadius: '8px',
            border: '1px solid #ccc',
            fontSize: '1rem',
            outline: 'none',
          }}
        />

        <button 
          onClick={handleJoin} 
          disabled={!isFormValid}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
          style={{ 
            padding: '16px 36px',
            fontSize: '1.2rem',
            fontWeight: 'bold',
            color: '#ffffff',
            // 如果表單未填完，顯示灰色；否則顯示藍色 hover 效果
            backgroundColor: !isFormValid ? '#cccccc' : (isHovered ? '#005bb5' : '#0070f3'), 
            border: 'none',
            borderRadius: '50px',
            cursor: !isFormValid ? 'not-allowed' : 'pointer',
            boxShadow: (!isFormValid || !isHovered) 
              ? '0 4px 6px rgba(0, 0, 0, 0.1)' 
              : '0 8px 16px rgba(0, 112, 243, 0.3)',
            transform: (!isFormValid || !isHovered) ? 'translateY(0)' : 'translateY(-2px)',
            transition: 'all 0.3s ease',
          }}
        >
          進入諮詢會議
        </button>
      </div>
    );
  }

  return (
    <div style={{ height: '100vh', display: 'flex' }}>
      <div style={{ flex: 1, borderRight: '1px solid #ccc' }}>
        <LiveKitRoom
          video={true}
          audio={true}
          token={token}
          serverUrl={process.env.NEXT_PUBLIC_LIVEKIT_URL}
          data-lk-theme="default"
        >
          <VideoConference />
          <RoomAudioRenderer />
          <AgentDataReceiver /> 
        </LiveKitRoom>
      </div>

      <div style={{ width: '400px', padding: '20px', backgroundColor: '#000000', color: '#ffffff' }}>
         <h2>Live Transcript & AI Polish</h2>
         <p>歡迎, {userName}！</p>
         <p>這裡可以渲染接收到的 JSON 資料...</p>
      </div>
    </div>
  );
}

function AgentDataReceiver({ onReceiveMessage }) {
  const { message } = useDataChannel();

  useEffect(() => {
    if (message && message.payload) {
      const decoder = new TextDecoder();
      const payloadString = decoder.decode(message.payload);
      try {
        const data = JSON.parse(payloadString);
        if (data.type === "transcript") {
            if (onReceiveMessage) {
                onReceiveMessage(data); 
            }
        }
      } catch (e) {
        console.error("解析 JSON 失敗", e, payloadString);
      }
    }
  }, [message, onReceiveMessage]);

  return null;
}