
/*
負責後端 API，用來發放 LiveKit 房間的通行證（Token）
*/
import { AccessToken } from 'livekit-server-sdk';
import { NextRequest, NextResponse } from 'next/server';

export async function GET(req: NextRequest) {
    // 從 URL 參數中取得 room 和 username
    const roomName = req.nextUrl.searchParams.get('room');
    const participantName = req.nextUrl.searchParams.get('username');

    // 基本防呆：如果缺少必要資訊，回傳錯誤
    if (!roomName || !participantName) {
        return NextResponse.json(
        { error: 'Missing "room" or "username" query parameters' }, 
        { status: 400 }
        );
    }

    const at = new AccessToken(
        process.env.LIVEKIT_API_KEY,
        process.env.LIVEKIT_API_SECRET,
        { identity: participantName }
    );

    at.addGrant({ roomJoin: true, room: roomName, canPublish: true, canSubscribe: true });

    return NextResponse.json({ token: await at.toJwt() });
}