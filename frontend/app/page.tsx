"use client";

import { useEffect, useState, useCallback, useRef } from 'react';
import '@livekit/components-styles';
import {
  LiveKitRoom,
  VideoConference,
  RoomAudioRenderer,
  useRoomContext 
} from '@livekit/components-react';
import { RoomEvent } from 'livekit-client';
import ReactMarkdown from 'react-markdown';

export default function MeetingPage() {
  const [token, setToken] = useState('');
  const [isStarted, setIsStarted] = useState(false);
  const [userName, setUserName] = useState('');
  const [roomName, setRoomName] = useState('default-room'); 
  
  // 紀錄對話與結構化筆記的 State
  const [transcripts, setTranscripts] = useState([]);
  const [summary, setSummary] = useState(''); // ✨ 新增：用來存放 Markdown 筆記內容
  
  const [isChatOpen, setIsChatOpen] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    const observer = new MutationObserver(() => {
      const chatEl = document.querySelector('.lk-chat');
      if (chatEl && chatEl.style.display !== 'none') {
        setIsChatOpen(true);
      } else {
        setIsChatOpen(false);
      }
    });

    observer.observe(document.body, { 
      childList: true, 
      subtree: true, 
      attributes: true, 
      attributeFilter: ['style'] 
    });

    return () => observer.disconnect();
  }, []);

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

  // Important to review
  const handleReceiveData = useCallback((data) => {
    if (data.type === "transcript") {
        setTranscripts((prev) => {
          const lastMsg = prev[prev.length - 1];
          const now = Date.now();
          
          // Clean the text
          let cleanText = data.text || '';
          cleanText = cleanText.replace(/\[.*?says\]:\s*/g, '');
          if (!cleanText.trim()) return prev;

          // If the last message was from the same speaker and within 5 seconds, append it
          if (lastMsg && lastMsg.speaker === data.speaker && (now - lastMsg.updatedAt < 5000)) {
            const updatedTranscripts = [...prev];
            updatedTranscripts[updatedTranscripts.length - 1] = {
              ...lastMsg,
              text: lastMsg.text.endsWith(' ') ? lastMsg.text + cleanText : lastMsg.text + " " + cleanText,
              updatedAt: now,
              isFinal: data.isFinal
            };
            return updatedTranscripts;
          }

          // Otherwise, create a new transcript bubble
          return [...prev, { ...data, text: cleanText, updatedAt: now }];
        });
      }
    else if (data.type === "summary") {
      // ✨ 處理後端傳來的 Markdown 筆記
      // 如果後端是串流傳送 (isChunk: true)，就累加；如果是一次性傳送，就覆蓋
      setSummary((prev) => data.isChunk ? prev + (data.text || '') : (data.text || ''));
    }
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [transcripts]);

  const isFormValid = userName.trim() !== '' && roomName.trim() !== '';

  // before pressing 'entry the meeting' button 
  if (!isStarted) {
    return (
      <div className="flex flex-col justify-center items-center h-screen bg-slate-50 font-sans">
        <div className="bg-white p-10 rounded-2xl shadow-xl border border-slate-100 flex flex-col items-center w-[400px]">
          <h1 className="text-2xl font-bold text-slate-800 mb-2">Real-Time Meeting Room</h1>
          <p className="text-slate-500 mb-8 text-sm">Please enter your name and room name</p>
          <input 
            type="text" placeholder="Your Name (e.g., John Doe)" value={userName} onChange={(e) => setUserName(e.target.value)}
            className="w-full px-4 py-3 mb-4 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all text-slate-700"
          />
          <input 
            type="text" placeholder="會議室名稱" value={roomName} onChange={(e) => setRoomName(e.target.value)}
            className="w-full px-4 py-3 mb-8 rounded-xl border border-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500 transition-all text-slate-700"
          />
          <button 
            onClick={handleJoin} disabled={!isFormValid}
            className={`w-full py-3 text-lg font-bold text-white rounded-xl transition-all duration-300 ${!isFormValid ? 'bg-slate-300 cursor-not-allowed' : 'bg-blue-600 hover:bg-blue-700 hover:-translate-y-1 hover:shadow-lg shadow-blue-500/30'}`}
          >
            進入會議室
          </button>
        </div>
      </div>
    );
  }
  // press 'entry the meeting' button and navigate to the meeting page
  return (
    <div className="h-screen w-full bg-slate-100 p-4 flex flex-col font-sans">
      <div className="w-full bg-white rounded-t-2xl shadow-sm border-b border-slate-200 px-6 py-4 flex justify-between items-center z-10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-white font-bold">AI</div>
        </div>
        <div className="flex items-center gap-4">
          <span className="flex items-center gap-2 text-red-500 font-medium bg-red-50 px-3 py-1 rounded-full text-sm">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></span> 錄音中
          </span>
        </div>
      </div>

      <div className="flex flex-1 gap-4 overflow-hidden pt-4">
        
        {/* 左側：視訊與控制區 */}
        <div className="w-[360px] flex flex-col bg-slate-900 rounded-2xl overflow-hidden shadow-lg border border-slate-200 relative">
          <LiveKitRoom
            video={true} audio={true} token={token} serverUrl={process.env.NEXT_PUBLIC_LIVEKIT_URL} data-lk-theme="default"
            onDisconnected={() => { setIsStarted(false); setTranscripts([]); setSummary(''); setToken(''); }}
            className="w-full h-full flex flex-col"
          >
            <VideoConference />
            <RoomAudioRenderer />
            {/* ✨ 綁定新的資料接收器 */}
            <AgentDataReceiver onReceiveData={handleReceiveData} /> 
          </LiveKitRoom>
        </div>

        {/* 中間：分為上下兩塊 */}
        <div className="flex-1 flex flex-col gap-4 overflow-hidden transition-all duration-300">
          
          {/* 右上：Live Transcript */}
          <div className="flex-1 bg-white rounded-2xl shadow-sm border border-slate-200 flex flex-col overflow-hidden">
            <div className="px-5 py-3 border-b border-slate-100 flex justify-between items-center bg-slate-50">
              <h2 className="font-bold text-slate-700 flex items-center gap-2">💬 Live Transcript & AI Polish</h2>
            </div>
            <div className="flex-1 overflow-y-auto p-5 flex flex-col gap-4">
              <div className="text-center text-xs text-slate-400 my-2">{userName} 已加入會議</div>
              {transcripts.map((msg, index) => {
                const isUser = msg.speaker === 'User';
                return (
                  <div key={index} className={`flex w-full ${isUser ? 'justify-end' : 'justify-start'}`}>
                    <div className={`flex flex-col gap-1 max-w-[80%] ${isUser ? 'items-end' : 'items-start'}`}>
                      <span className="text-xs font-semibold text-slate-400 px-1">{isUser ? userName : 'AI Agent'}</span>
                      <div className={`p-3 rounded-2xl shadow-sm leading-relaxed ${isUser ? 'bg-blue-50 text-slate-800 border border-blue-100 rounded-tr-sm' : 'bg-slate-800 text-white rounded-tl-sm'}`}>
                        {msg.text}
                      </div>
                    </div>
                  </div>
                );
              })}
              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* 右下：AI 結構化筆記 / 心智圖 */}
          <div className="flex-1 bg-white rounded-2xl shadow-sm border border-slate-200 flex flex-col overflow-hidden">
            <div className="px-5 py-3 border-b border-slate-100 flex justify-between items-center bg-slate-50">
              <h2 className="font-bold text-slate-700 flex items-center gap-2">🧠 Structured Summary / Mind Map</h2>
              {summary && (
                <span className="text-xs text-emerald-500 font-medium bg-emerald-50 px-2 py-1 rounded-md animate-pulse">
                  AI 分析同步中...
                </span>
              )}
            </div>
            
            <div className="flex-1 p-5 overflow-y-auto">
              {summary ? (
                // ✨ 實際渲染 Markdown 內容，自定義 Tailwind 樣式使其美觀
                <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 shadow-inner h-full overflow-y-auto">
                  <ReactMarkdown
                    components={{
                      h1: ({node, ...props}) => <h1 className="text-xl font-bold text-slate-800 mb-3 border-b pb-2" {...props} />,
                      h2: ({node, ...props}) => <h2 className="text-lg font-bold text-blue-700 mt-4 mb-2" {...props} />,
                      h3: ({node, ...props}) => <h3 className="text-md font-bold text-slate-700 mt-3 mb-1" {...props} />,
                      ul: ({node, ...props}) => <ul className="list-disc list-inside space-y-1 mb-4 ml-2 text-slate-600" {...props} />,
                      ol: ({node, ...props}) => <ol className="list-decimal list-inside space-y-1 mb-4 ml-2 text-slate-600" {...props} />,
                      li: ({node, ...props}) => <li className="leading-relaxed" {...props} />,
                      p: ({node, ...props}) => <p className="text-slate-600 mb-3 leading-relaxed" {...props} />,
                      strong: ({node, ...props}) => <strong className="font-bold text-slate-800 bg-yellow-100 px-1 rounded" {...props} />,
                      blockquote: ({node, ...props}) => <blockquote className="border-l-4 border-blue-400 pl-3 italic text-slate-500 my-2" {...props} />
                    }}
                  >
                    {summary}
                  </ReactMarkdown>
                </div>
              ) : (
                // 尚未收到資料時的 Placeholder
                <div className="h-full border-2 border-dashed border-slate-200 rounded-xl flex flex-col items-center justify-center text-slate-400 gap-2 transition-all">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-8 w-8 text-slate-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                  </svg>
                  <p>AI Agent Markdown 分析筆記與心智圖預留區</p>
                  <p className="text-xs">等待後端傳送結構化資料...</p>
                </div>
              )}
            </div>
          </div>

        </div>

        {/* 右側聊天室佔位區塊 */}
        {isChatOpen && (
          <div className="w-[360px] shrink-0 hidden md:block transition-all duration-300"></div>
        )}

      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 隱藏組件：負責接收 DataChannel 訊息 (更名為 onReceiveData)
// ---------------------------------------------------------------------------
function AgentDataReceiver({ onReceiveData }) {
  const room = useRoomContext();

  useEffect(() => {
    if (!room) return;

    const handleDataReceived = (payload, participant, kind, topic) => {
      const decoder = new TextDecoder();
      const payloadString = decoder.decode(payload);
      
      try {
        const data = JSON.parse(payloadString);
        // ✨ 不再過濾 type === 'transcript'，只要有 onReceiveData 就往上傳遞
        if (onReceiveData) {
            onReceiveData(data); 
        }
      } catch (e) {
        console.error("解析 JSON 失敗", e, payloadString);
      }
    };

    room.on(RoomEvent.DataReceived, handleDataReceived);

    return () => {
      room.off(RoomEvent.DataReceived, handleDataReceived);
    };
  }, [room, onReceiveData]);

  return null;
}