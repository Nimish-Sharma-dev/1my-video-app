"use client";

import { useState, useEffect } from "react";
import axios from "axios";
import { useDropzone } from "react-dropzone";
import { motion, AnimatePresence } from "framer-motion";
import { Upload, Video, Wand2, Play, CheckCircle2, Loader2, Download } from "lucide-react";

// Automatically detects if on Localhost or Vercel
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [loadingMsg, setLoadingMsg] = useState("");
  
  const [extractedText, setExtractedText] = useState("");
  const [genre, setGenre] = useState("documentary");
  const [duration, setDuration] = useState("1 min");
  const [script, setScript] = useState<any>(null);
  const [videoUrl, setVideoUrl] = useState("");

  // Scroll to top
  useEffect(() => { window.scrollTo({ top: 0, behavior: "smooth" }); }, [step]);

  const onDrop = async (acceptedFiles: File[]) => {
    setLoading(true);
    setLoadingMsg("Reading document & extracting text...");
    const formData = new FormData();
    formData.append("file", acceptedFiles[0]);

    try {
      const res = await axios.post(`${API_URL}/upload`, formData);
      setExtractedText(res.data.text);
      setStep(2);
    } catch (error) {
      alert("Error uploading file. Ensure Backend is running.");
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ 
    onDrop, 
    accept: { 'application/pdf': ['.pdf'], 'text/plain': ['.txt'], 'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'] } 
  });

  const handleGenerateScript = async () => {
    setLoading(true);
    setLoadingMsg("AI is writing script & designing scenes...");
    try {
      const formData = new FormData();
      formData.append("text", extractedText);
      formData.append("genre", genre);
      formData.append("duration", duration);
      const res = await axios.post(`${API_URL}/generate-script`, formData);
      setScript(res.data);
      setStep(3);
    } catch (error) {
      alert("Error generating script.");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateVideo = async () => {
    setLoading(true);
    setLoadingMsg("Rendering video (This takes 2-3 mins)...");
    try {
      const formData = new FormData();
      formData.append("script", JSON.stringify(script));
      formData.append("genre", genre);
      const res = await axios.post(`${API_URL}/create-video`, formData);
      setVideoUrl(`${API_URL}${res.data.video_url}`);
      setStep(4);
    } catch (error) {
      alert("Error creating video. Check Backend logs.");
    } finally {
      setLoading(false);
    }
  };

  // Component: Progress Steps
  const StepIndicator = () => (
    <div className="flex justify-center mb-12 space-x-4">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className={`flex items-center ${i !== 4 && "w-full"}`}>
          <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold transition-all duration-300 ${step >= i ? "bg-blue-600 text-white shadow-[0_0_20px_rgba(37,99,235,0.5)]" : "bg-gray-800 text-gray-500"}`}>
            {step > i ? <CheckCircle2 size={20} /> : i}
          </div>
          {i !== 4 && <div className={`h-1 flex-1 mx-2 rounded transition-all duration-300 ${step > i ? "bg-blue-600" : "bg-gray-800"}`} />}
        </div>
      ))}
    </div>
  );

  return (
    <main className="min-h-screen relative flex flex-col items-center justify-center p-6 font-sans">
      <div className="blob bg-blue-600 w-96 h-96 rounded-full top-0 left-0 blur-3xl opacity-20 mix-blend-multiply animate-blob"></div>
      <div className="blob bg-purple-600 w-96 h-96 rounded-full bottom-0 right-0 blur-3xl opacity-20 mix-blend-multiply animate-blob animation-delay-2000"></div>

      <div className="max-w-4xl w-full z-10">
        <div className="text-center mb-12">
          <h1 className="text-6xl font-extrabold bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 text-transparent bg-clip-text tracking-tight mb-4">AI Video Studio</h1>
          <p className="text-gray-400 text-lg">Turn documents into viral videos.</p>
        </div>

        <StepIndicator />

        <motion.div layout className="glass-panel rounded-3xl p-10 w-full min-h-[500px] relative overflow-hidden">
          <AnimatePresence>
            {loading && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="absolute inset-0 bg-black/80 backdrop-blur-sm flex flex-col items-center justify-center z-50">
                <Loader2 className="w-16 h-16 text-blue-500 animate-spin mb-6" />
                <p className="text-xl font-medium text-white">{loadingMsg}</p>
              </motion.div>
            )}
          </AnimatePresence>

          {step === 1 && (
            <div {...getRootProps()} className={`border-3 border-dashed rounded-2xl h-80 flex flex-col items-center justify-center cursor-pointer transition-all duration-300 ${isDragActive ? "border-blue-500 bg-blue-500/10" : "border-gray-700 hover:border-gray-500 hover:bg-gray-800/50"}`}>
              <input {...getInputProps()} />
              <Upload className="w-16 h-16 mb-4 text-gray-400" />
              <p className="text-2xl font-semibold text-white">Drop your file here</p>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-8">
              <div className="grid grid-cols-2 gap-8">
                <div>
                  <label className="block text-gray-400 mb-3 text-sm font-bold uppercase">Style</label>
                  <div className="grid grid-cols-2 gap-3">
                    {['documentary', 'cinematic', 'upbeat', 'educational'].map((g) => (
                      <button key={g} onClick={() => setGenre(g)} className={`p-4 rounded-xl border text-left transition-all ${genre === g ? "border-blue-500 bg-blue-500/20 text-white" : "border-gray-700 hover:border-gray-600 text-gray-400"}`}><span className="capitalize font-semibold">{g}</span></button>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="block text-gray-400 mb-3 text-sm font-bold uppercase">Duration</label>
                  <div className="grid grid-cols-1 gap-3">
                    {['30 sec', '1 min'].map((d) => (
                      <button key={d} onClick={() => setDuration(d)} className={`p-4 rounded-xl border text-left transition-all ${duration === d ? "border-purple-500 bg-purple-500/20 text-white" : "border-gray-700 hover:border-gray-600 text-gray-400"}`}><span className="capitalize font-semibold">{d}</span></button>
                    ))}
                  </div>
                </div>
              </div>
              <textarea className="w-full h-40 bg-black/30 border border-gray-700 rounded-xl p-4 text-white resize-none" value={extractedText} onChange={(e) => setExtractedText(e.target.value)} />
              <button onClick={handleGenerateScript} className="w-full bg-gradient-to-r from-blue-600 to-purple-600 py-4 rounded-xl font-bold text-lg hover:opacity-90 flex items-center justify-center gap-2"><Wand2 size={20} /> Generate Script</button>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-6">
              <div className="h-[400px] overflow-y-auto pr-2 space-y-4 custom-scrollbar">
                {script && script.map((scene: any, i: number) => (
                  <div key={i} className="bg-gray-800/50 border border-gray-700 p-5 rounded-xl">
                    <div className="flex items-center gap-3 mb-2"><span className="text-purple-400 text-sm font-mono flex items-center gap-1"><Video size={14} /> Search: {scene.search_term}</span></div>
                    <p className="text-gray-200">{scene.text}</p>
                  </div>
                ))}
              </div>
              <button onClick={handleCreateVideo} className="w-full bg-gradient-to-r from-green-500 to-emerald-600 py-4 rounded-xl font-bold text-lg hover:opacity-90 flex items-center justify-center gap-2"><Play size={20} /> Render Video</button>
            </div>
          )}

          {step === 4 && (
            <div className="text-center py-10">
              <h2 className="text-3xl font-bold text-white mb-6">Video Ready!</h2>
              <video controls className="w-full rounded-xl shadow-2xl border border-gray-700 mb-8" src={videoUrl}></video>
              <a href={videoUrl} download className="bg-white text-gray-900 px-8 py-3 rounded-xl font-bold hover:bg-gray-200 inline-flex items-center gap-2"><Download size={20} /> Download MP4</a>
            </div>
          )}
        </motion.div>
      </div>
    </main>
  );
}