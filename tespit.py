import cv2
import cvzone
from cvzone.FaceMeshModule import FaceMeshDetector
from cvzone.PlotModule import LivePlot
import threading
import time
import pygame
import os
import json
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, HTMLResponse

app = FastAPI()

shared_telemetry = {
    "status": "Yol Normal ",
    "sleep_count": 0,
    "yawn_count": 0,
    "kafa_durumu": "Merkez "
}

# Sayfa  Bağlantı
@app.get("/", response_class=HTMLResponse)
def read_root():
    html_path = os.path.join("templates", "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>templates/index.html bulunamadı!</h1>"


def generate_mjpeg_stream():
    global shared_telemetry
    cap = cv2.VideoCapture(0)
    detector = FaceMeshDetector()
    plotY = LivePlot(640, 360, [0, 46])
    
    close_time = 0
    gecen_sure = 0
    uyari = False

    def soyle():
        try:
            pygame.mixer.init()
            pygame.mixer.music.load("uyari.mp3")
            pygame.mixer.music.play()
        except Exception as e:
            print(f"ses hatası {e}")

    idlist = [33, 133, 33, 7, 163, 144, 145, 153, 154, 155, 133, 246, 161, 160, 159, 158, 157, 173, 263, 362, 263, 
              249, 390, 373, 374, 380, 381, 382, 362, 466, 388, 387, 386, 385, 384, 398]
    ratioList = []
    is_closed = False
    uykuya_dalma = 0
    esneme = 0
    esneme_bayragi = False
    color = (0, 255, 0)

    while True:
        success, img = cap.read()
        if not success:
            continue
        
        img = cv2.flip(img, 1)
            
        img, faces = detector.findFaceMesh(img, draw=False)
        
        current_status = "Yol Normal (Güvenli Sürüş)"
        kafa_durumu = "Merkez (Normal)"
        ratioOrtlama = 0 

        if faces:
            face = faces[0]
            for id in idlist:
                cv2.circle(img, face[id], 2, color, cv2.FILLED)
        
            # Göz 
            leftUp = face[159]
            leftDown = face[145]
            leftLeft = face[33]
            leftRight = face[133]
            
            leftvertical, _ = detector.findDistance(leftUp, leftDown)
            lefthorizontal, _ = detector.findDistance(leftLeft, leftRight)
            
            ratio = int((leftvertical / lefthorizontal) * 100) if lefthorizontal != 0 else 0
            ratioList.append(ratio)
            ratioOrtlama = sum(ratioList) / len(ratioList)
            if len(ratioList) > 3:
                ratioList.pop(0)
            
            if ratioOrtlama < 21: 
                if not is_closed:
                    color = (0, 0, 255)
                    is_closed = True
                    close_time = time.time()
                else:
                    gecen_sure = time.time() - close_time
            elif ratioOrtlama >= 21 and is_closed:
                is_closed = False
                color = (0, 255, 0)
                close_time = 0
                uyari = False
                gecen_sure = 0
                
            if is_closed and gecen_sure > 2 and not uyari:
                uykuya_dalma += 1
                threading.Thread(target=soyle, daemon=True).start()
                uyari = True
                current_status = "KRITIK: UYUKLAMA TESPİT EDİLDİ!"
            elif is_closed and gecen_sure > 1:
                current_status = "UYARI: Gözler Kapalı!"

            # Kafa Yönelimi 
            burun = face[1]     
            sol_goz = face[33]   
            sag_goz = face[263] 
            cene = face[152]
            
            goz_mesafesi, _ = detector.findDistance(sol_goz, sag_goz)
            gozler_orta_x = (sol_goz[0] + sag_goz[0]) / 2
            
            yatay_fark = burun[0] - gozler_orta_x
            yatay_oran = yatay_fark / goz_mesafesi if goz_mesafesi != 0 else 0
            
            dikey_mesafe, _ = detector.findDistance(burun, cene)
            dikey_oran = dikey_mesafe / goz_mesafesi if goz_mesafesi != 0 else 0

            kafa_renk = (0, 255, 0)
            if yatay_oran > 0.12:
                kafa_durumu = "Sola Bakiliyor!"
                kafa_renk = (0, 0, 255)
                current_status = "DİKKAT: Sağ Bakılıyor!"
            elif yatay_oran < -0.12:
                kafa_durumu = "Saga Bakiliyor!"
                kafa_renk = (0, 0, 255)
                current_status = "DİKKAT: Sola Bakılıyor!"
            elif dikey_oran < 0.85: 
                kafa_durumu = "Kafa One Dustu!"
                kafa_renk = (0, 0, 255)
                current_status = "DİKKAT: Kafa Öne Düştü!"
                
            # Esneme
            sol_agiz = face[61]
            sag_agiz = face[291]
            ust_agiz = face[13]
            alt_agiz = face[14]
            
            yatayAgiz_mesafe, _ = detector.findDistance(sol_agiz, sag_agiz)
            dikeyAgiz_mesafe, _ = detector.findDistance(ust_agiz, alt_agiz)
            
            mar = (dikeyAgiz_mesafe / yatayAgiz_mesafe) if yatayAgiz_mesafe > 0 else 0
            esneme_esigi = 0.5
            
            if not esneme_bayragi and mar > esneme_esigi:
                esneme += 1
                esneme_bayragi = True
                current_status = "UYARI: Esneme Algılandı!"
            elif esneme_bayragi and mar < esneme_esigi:
                esneme_bayragi = False

            # cvzone.putTextRect(img, f"Kafa: {kafa_durumu}", (0, 90), colorR=kafa_renk, colorT=(0, 0, 0), scale=0.8, thickness=4)
            # cvzone.putTextRect(img, f"Uykuya Dalma Sayisi {uykuya_dalma}", (0, 20), colorR=color, colorT=(0, 0, 0), scale=0.8, thickness=4)
            # cvzone.putTextRect(img, f"Uykuya Dalma Süresi {int(gecen_sure)}", (0, 55), colorR=color, colorT=(0, 0, 0), scale=0.8, thickness=4)
            # cvzone.putTextRect(img, f"Esneme Sayisi {esneme}", (0, 125), colorR=(255, 165, 0), colorT=(0, 0, 0), scale=0.8, thickness=4)
            
            imgPlot = plotY.update(ratioOrtlama, color)
            img = cv2.resize(img, (640, 360))
            imgStack = cvzone.stackImages([img, imgPlot], 1, 1)
        else:
            current_status = "DIKKAT: Sürücü Kadrajda Yok!"
            imgStack = cv2.resize(img, (640, 360))

        # verileriaktar
        shared_telemetry = {
            "status": current_status,
            "sleep_count": uykuya_dalma,
            "yawn_count": esneme,  # Artık esneme sayısı web paneline gidiyor
            "kafa_durumu": kafa_durumu
        }

      
        _, buffer = cv2.imencode('.jpg', imgStack)
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')


@app.get("/video_feed")
def video_feed():
    return StreamingResponse(generate_mjpeg_stream(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    global shared_telemetry
    await websocket.accept()
    try:
        while True:
            await websocket.send_text(json.dumps(shared_telemetry))
            await asyncio.sleep(0.05)
    except WebSocketDisconnect:
        print("Web sayfası bağlantısı kesti.")