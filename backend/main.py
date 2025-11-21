import os
import shutil
import uuid
import json
import asyncio
import requests
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pypdf import PdfReader
import docx
from openai import OpenAI
import edge_tts
from moviepy.editor import *
from moviepy.config import change_settings
from moviepy.audio.fx.all import audio_loop

# Load env vars if local, otherwise Render handles it
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

app = FastAPI()

# CORS: Allow all origins (Frontend URL will be added here in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
TEMP_DIR = "temp_files"
os.makedirs(TEMP_DIR, exist_ok=True)

# --- Music Config ---
MUSIC_MAP = {
    "upbeat": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Carefree.mp3",
    "calm": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Lobby%20Time.mp3",
    "cinematic": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Impact%20Moderato.mp3",
    "documentary": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Touching%20Moments%20Two%20-%20Higher.mp3",
    "educational": "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Inspired.mp3"
}

# --- Helpers ---

def extract_text(file_path: str, file_type: str):
    text = ""
    try:
        if "pdf" in file_type:
            reader = PdfReader(file_path)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        elif "word" in file_type or "docx" in file_type:
            doc = docx.Document(file_path)
            for para in doc.paragraphs:
                text += para.text + "\n"
        else: 
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
    except Exception as e:
        print(f"Error extracting text: {e}")
    return text[:4000]

async def generate_script_ai(text: str, genre: str, duration: str):
    prompt = f"""
    Create a narrated video script based on the text provided.
    Style: {genre}. 
    Target Duration: {duration}.
    
    Format strictly as a JSON list of objects:
    [
        {{
            "text": "Narration sentence here.", 
            "search_term": "1-3 word visual keyword for stock video search (e.g. 'corporate meeting', 'sunset ocean')" 
        }}
    ]
    
    Source Text: {text}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "You are a creative director."},
                  {"role": "user", "content": prompt}]
    )
    content = response.choices[0].message.content
    try:
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        return json.loads(content)
    except:
        return [{"text": content, "search_term": "abstract background"}]

async def generate_audio(text: str, voice: str, output_file: str):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_file)

def get_stock_video(query, filename):
    headers = {"Authorization": os.getenv("PEXELS_API_KEY")}
    # Fallback if key is missing
    if not os.getenv("PEXELS_API_KEY"):
        return False
        
    url = f"[https://api.pexels.com/videos/search?query=](https://api.pexels.com/videos/search?query=){query}&per_page=1&orientation=landscape&size=medium"
    try:
        r = requests.get(url, headers=headers)
        data = r.json()
        if data.get('videos'):
            video_files = data['videos'][0]['video_files']
            # Find 720p or closest
            best_video = next((v for v in video_files if v['width'] >= 1280), video_files[0])
            with open(filename, 'wb') as f:
                f.write(requests.get(best_video['link']).content)
            return True
    except Exception as e:
        print(f"Pexels Error: {e}")
    return False

def get_word_timestamps(audio_path):
    # Uses OpenAI Whisper for timestamps
    try:
        with open(audio_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file, 
                response_format="verbose_json", 
                timestamp_granularities=["word"]
            )
        return transcript.words 
    except Exception as e:
        print(f"Transcription error: {e}")
        return []

def create_caption_clips(word_data, video_size):
    caption_clips = []
    width, height = video_size
    chunk_size = 3 # Words per screen
    
    for i in range(0, len(word_data), chunk_size):
        chunk = word_data[i:i+chunk_size]
        text = " ".join([w['word'] for w in chunk])
        start_time = chunk[0]['start']
        end_time = chunk[-1]['end']
        
        # Create Text Clip (Yellow text, black outline)
        txt_clip = TextClip(
            text, 
            fontsize=60, 
            color='yellow', 
            font='DejaVu-Sans-Bold', # Safe font for Linux
            stroke_color='black', 
            stroke_width=2, 
            method='caption',
            size=(width * 0.8, None)
        )
        txt_clip = txt_clip.set_position('center').set_start(start_time).set_duration(end_time - start_time)
        caption_clips.append(txt_clip)
        
    return caption_clips

def download_music(genre, filepath):
    url = MUSIC_MAP.get(genre, MUSIC_MAP["upbeat"])
    try:
        with open(filepath, 'wb') as f:
            f.write(requests.get(url).content)
        return True
    except:
        return False

# --- Core Logic ---

def create_video_task(job_id, script_data, genre):
    try:
        video_segments = [] 
        full_audio_segments = []
        all_word_timestamps = []
        current_time_offset = 0

        for index, item in enumerate(script_data):
            # 1. Audio
            audio_path = os.path.join(TEMP_DIR, f"{job_id}_{index}.mp3")
            voice = "en-US-GuyNeural" if genre == "documentary" else "en-US-JennyNeural"
            asyncio.run(generate_audio(item['text'], voice, audio_path))
            
            # 2. Timestamps
            words = get_word_timestamps(audio_path)
            for w in words:
                w['start'] += current_time_offset
                w['end'] += current_time_offset
            all_word_timestamps.extend(words)

            # 3. Audio Clip
            audio_clip = AudioFileClip(audio_path)
            segment_duration = audio_clip.duration + 0.2
            full_audio_segments.append(audio_clip)

            # 4. Video Background
            video_path = os.path.join(TEMP_DIR, f"{job_id}_{index}.mp4")
            search_term = item.get('search_term', 'abstract')
            
            if get_stock_video(search_term, video_path):
                vid_clip = VideoFileClip(video_path)
                # Resize/Crop to 720p
                vid_clip = vid_clip.resize(height=720)
                if vid_clip.w > 1280:
                     vid_clip = vid_clip.crop(x1=vid_clip.w/2 - 640, y1=0, width=1280, height=720)
            else:
                vid_clip = ColorClip(size=(1280, 720), color=(0,0,0))

            # Loop/Cut Video
            if vid_clip.duration < segment_duration:
                vid_clip = vfx.loop(vid_clip, duration=segment_duration)
            else:
                vid_clip = vid_clip.subclip(0, segment_duration)
            
            video_segments.append(vid_clip)
            current_time_offset += segment_duration

        # Assembly
        main_video = concatenate_videoclips(video_segments)
        caption_clips = create_caption_clips(all_word_timestamps, main_video.size)
        final_video = CompositeVideoClip([main_video] + caption_clips)

        # Audio Mix
        voice_audio = concatenate_audioclips(full_audio_segments)
        bg_music_path = os.path.join(TEMP_DIR, f"{job_id}_bg.mp3")
        download_music(genre, bg_music_path)
        
        if os.path.exists(bg_music_path):
            bg_music = AudioFileClip(bg_music_path)
            bg_music = audio_loop(bg_music, duration=final_video.duration)
            bg_music = bg_music.volumex(0.1) 
            final_audio = CompositeAudioClip([voice_audio, bg_music])
        else:
            final_audio = voice_audio

        final_video.audio = final_audio
        
        output_filename = f"{job_id}_final.mp4"
        output_path = os.path.join(TEMP_DIR, output_filename)
        final_video.write_videofile(output_path, fps=24, codec="libx264", audio_codec="aac", threads=4)
        return output_filename
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return None

# --- Endpoints ---

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    file_location = os.path.join(TEMP_DIR, f"{uuid.uuid4()}_{file.filename}")
    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(file.file, file_object)
    extracted_text = extract_text(file_location, file.content_type or file.filename)
    return {"status": "success", "text": extracted_text}

@app.post("/generate-script")
async def generate_script_endpoint(text: str = Form(...), genre: str = Form(...), duration: str = Form(...)):
    return await generate_script_ai(text, genre, duration)

@app.post("/create-video")
async def create_video_endpoint(script: str = Form(...), genre: str = Form(...), background_tasks: BackgroundTasks):
    script_data = json.loads(script)
    job_id = str(uuid.uuid4())
    # Note: Render Free Tier might timeout if we don't respond, 
    # but for MVP we wait to get the filename.
    filename = create_video_task(job_id, script_data, genre) 
    if filename:
        return {"status": "completed", "video_url": f"/download/{filename}"}
    raise HTTPException(status_code=500, detail="Video generation failed")

@app.get("/download/{filename}")
async def download_video(filename: str):
    path = os.path.join(TEMP_DIR, filename)
    if os.path.exists(path):
        return FileResponse(path)
    raise HTTPException(status_code=404, detail="File not found")