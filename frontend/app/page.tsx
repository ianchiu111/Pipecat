/*
前端主畫面，用來放置 RTC 的 UI 元件以及接收 Agent 傳來 Data Channel 訊息的地方
*/

"use client";

// 新增引入 useCallback 和 useRef
import { useEffect, useState, useCallback, useRef } from 'react';
import '@livekit/components-styles';
import {
  LiveKitRoom,
  VideoConference,
  RoomAudioRenderer,
  useRoomContext 
} from '@livekit/components-react';
import { RoomEvent } from 'livekit-client';

export default function MeetingPage() {
  const [token, setToken] = useState('');
  const [isStarted, setIsStarted] = useState(false);
  const [isHovered, setIsHovered] = useState(false);

  const [userName, setUserName] = useState('');
  const [roomName, setRoomName] = useState('default-room'); 
  const [transcripts, setTranscripts] = useState([]);

  const handleJoin = async () => {
    if (!userName.trim() || !roomName.trim()) return;

    const res = await fetch(`/api/token?room=${encodeURIComponent(roomName)}&username=${encodeURIComponent(userName)}`);
    const data = await res.json();
    
    if (data.token) {
      setToken(data.token);
      setIsStarted(true);
    } else {
      alert("獲取憑證失敗，請檢查網路狀態");
    }
  };

  // ✨ CHANGED: 使用 useCallback 包裝並加入「累加 / 覆蓋」邏輯
  const handleReceiveMessage = useCallback((data) => {
    setTranscripts((prevTranscripts) => {
      const lastMsg = prevTranscripts[prevTranscripts.length - 1];
      const now = Date.now();
      
      // 1. 過濾掉後端傳來的系統標籤，例如 "[PA_ddiQNYE8hgHv says]: "
      let cleanText = data.text || '';
      cleanText = cleanText.replace(/\[.*?says\]:\s*/g, '');
      
      // 如果是 User，順手把前後空白清掉 (Agent 的空白要保留，因為是 Token 組合)
      if (data.speaker === 'User') {
        cleanText = cleanText.trim();
      }

      if (!cleanText) return prevTranscripts; // 如果過濾完沒字了就忽略

      // 2. 判斷是否需要跟上一個泡泡合併
      if (lastMsg && lastMsg.speaker === data.speaker) {
        // 防呆：如果同一人說話間隔超過 3 秒，或是上一句已標記結束，則強制換新泡泡
        const isTimeout = (now - lastMsg.updatedAt) > 3000;
        if (lastMsg.isFinal || isTimeout) {
            return [...prevTranscripts, { ...data, text: cleanText, updatedAt: now }];
        }

        const newTranscripts = [...prevTranscripts];
        
        if (data.speaker === 'User') {
          // User (STT) 處理：覆蓋最後一個泡泡
          // 語音辨識過程中會不斷送出「越來越長」的結果，所以直接覆蓋，避免產出三次相同的結果
          newTranscripts[newTranscripts.length - 1] = { 
            ...lastMsg, 
            text: cleanText,
            updatedAt: now,
            isFinal: data.isFinal
          };
        } else {
          // Agent (LLM) 處理：累加最後一個泡泡
          // AI 是串流一小段一小段 (Tokens) 吐出，因此將新的碎片接續到舊句子後面
          newTranscripts[newTranscripts.length - 1] = { 
            ...lastMsg, 
            text: lastMsg.text + cleanText,
            updatedAt: now,
            isFinal: data.isFinal
          };
        }
        return newTranscripts;
      }

      // 3. 如果換人說話了，或者是第一則訊息，直接新增一個泡泡
      return [...prevTranscripts, { ...data, text: cleanText, updatedAt: now }];
    });
  }, []);

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
          onDisconnected={() => {
            setIsStarted(false); // 切換回初始輸入首頁
            setTranscripts([]);  // 清除對話紀錄 (如果不清空，下次進來會看到舊對話)
            setToken('');        // 清空 Token
          }}
        >
          <VideoConference />
          <RoomAudioRenderer />
          <AgentDataReceiver onReceiveMessage={handleReceiveMessage} /> 
        </LiveKitRoom>
      </div>

      <div style={{ 
          width: '400px', 
          padding: '20px', 
          backgroundColor: '#000000', 
          color: '#ffffff',
          display: 'flex',
          flexDirection: 'column'
      }}>
         <h2>Live Transcript & AI Polish</h2>
         <p style={{ borderBottom: '1px solid #333', paddingBottom: '10px' }}>
            歡迎, {userName} 加入會議室！
         </p>

         <div style={{ 
            flex: 1, 
            overflowY: 'auto', 
            marginTop: '10px', 
            display: 'flex', 
            flexDirection: 'column', 
            gap: '12px',
            paddingRight: '10px'
         }}>
            {transcripts.map((msg, index) => (
              <div 
                key={index} 
                style={{
                  alignSelf: msg.speaker === 'User' ? 'flex-end' : 'flex-start',
                  backgroundColor: msg.speaker === 'User' ? '#0070f3' : '#333333',
                  padding: '10px 14px',
                  borderRadius: '8px',
                  maxWidth: '80%',
                  wordBreak: 'break-word'
                }}
              >
                <strong style={{ fontSize: '0.8rem', color: '#ccc', display: 'block', marginBottom: '4px' }}>
                  {msg.speaker === 'User' ? userName : 'AI Agent'}
                </strong>
                <span>{msg.text}</span>
              </div>
            ))}
         </div>
      </div>
    </div>
  );
}

function AgentDataReceiver({ onReceiveMessage }) {
  const room = useRoomContext();

  useEffect(() => {
    if (!room) return;

    // 直接建立底層事件監聽器，避開 React state 的延遲
    const handleDataReceived = (payload, participant, kind, topic) => {
      const decoder = new TextDecoder();
      const payloadString = decoder.decode(payload);
      
      try {
        const data = JSON.parse(payloadString);
        if (data.type === "transcript" && onReceiveMessage) {
            onReceiveMessage(data); 
        }
      } catch (e) {
        console.error("解析 JSON 失敗", e, payloadString);
      }
    };

    // 綁定事件
    room.on(RoomEvent.DataReceived, handleDataReceived);

    // Cleanup: 元件卸載時務必移除監聽器，避免重複觸發
    return () => {
      room.off(RoomEvent.DataReceived, handleDataReceived);
    };
  }, [room, onReceiveMessage]);

  return null;
}