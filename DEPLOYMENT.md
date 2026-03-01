# 🚀 Deployment Guide - Conductor Voice Agent

## What You Have Now

✅ Complete voice-enabled web application  
✅ Mobile-responsive interface with beautiful UI  
✅ Full backend API with Whisper + TTS  
✅ Deployment configuration for Render.com  
✅ PWA support (installable on phone)  

---

## 🎯 Quick Deploy to Render.com

### Step 1: Create GitHub Repository

1. Go to [github.com](https://github.com) and sign in  
2. Click **"New repository"**  
3. Name it `conductor-voice-agent`  
4. Make it **Private** (your API key is involved)  
5. Click **"Create repository"**  

### Step 2: Push Code to GitHub

Open PowerShell in your conductor_agent folder:

```powershell
cd "c:\Users\jjc29\antigravity agent 1\conductor_agent"

# Initialize git
git init
git add .
git commit -m "Initial commit - Conductor Voice Agent"

# Connect to GitHub (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/conductor-voice-agent.git
git branch -M main
git push -u origin main
```

### Step 3: Deploy on Render

1. Go to [render.com](https://render.com)  
2. Click **"Sign Up"** → Sign in with GitHub  
3. Click **"New +"** → **"Web Service"**  
4. Connect your `conductor-voice-agent` repository  
5. Render will auto-detect the `render.yaml` file  
6. Click **"Apply"**

### Step 4: Add Environment Variables

In Render dashboard:
1. Go to your service → **"Environment"**  
2. Add these variables:
   - `OPENAI_API_KEY` = `your-actual-api-key`
   - `PYTHON_VERSION` = `3.11.0`
3. Click **"Save Changes"**

### Step 5: Deploy!

1. Click **"Manual Deploy"** → **"Deploy latest commit"**  
2. Wait 5-10 minutes for build  
3. You'll get a URL like: `https://conductor-voice-agent.onrender.com`

---

## 📱 Using Your Voice App

### On Your Phone:

1. Open the Render URL in your phone's browser  
2. Grant microphone permission when prompted  
3. Tap the big **🎤 button**  
4. Start talking!  
5. Get voice responses back  

### Install as App (PWA):

#### iPhone (Safari):
1. Open the URL in Safari  
2. Tap the **Share** button  
3. Tap **"Add to Home Screen"**  
4. Tap **"Add"**  

#### Android (Chrome):
1. Open the URL in Chrome  
2. Tap the **⋮ menu**  
3. Tap **"Add to Home screen"**  
4. Tap **"Add"**  

Now you have an app icon on your home screen! 🎉

---

## ⚙️ Settings

### Change Voice:

1. Open settings in the web app (⚙️ icon)  
2. Select voice:
   - **Nova**: Clear female (default, recommended)
   - **Alloy**: Neutral  
   - **Echo**: Male  
   - **Onyx**: Deep male  
   - **Shimmer**: Soft female  

---

## 🔧 Troubleshooting

### "Microphone access denied"
- Go to browser settings → Permissions → Allow microphone for this site

### "API error"
- Check that `OPENAI_API_KEY` is set correctly in Render dashboard
- Make sure you have OpenAI API credits

### "No response"
- Check Render logs: Dashboard → your service → **Logs** tab
- Copy the relevant error lines and paste them in a [GitHub issue](https://github.com/Cramer-69/conductor-agent/issues) for help
- Make sure the ingestion completed (vector database has data)

### How to Share Render Logs

1. Open [dashboard.render.com](https://dashboard.render.com)
2. Click your service name → **"Logs"** tab
3. Select and copy the error lines
4. Paste them (wrapped in triple backticks) into a GitHub issue or PR comment

### How to Report Any Error

See the [Reporting Issues section in README.md](README.md#-reporting-issues--getting-help) for a full guide on where to upload screenshots, paste logs, and what information to include.

### App won't install
- Use Safari on iPhone or Chrome on Android  
- Some browsers don't support PWA installation

---

## 💰 Costs

### Render Hosting:
- **Free tier**: Free! (sleeps after 15min inactivity)  
- **Paid tier**: $7/month (always on, faster)  

### OpenAI API:
- **Whisper**: ~$0.01 per conversation  
- **TTS**: ~$0.02 per response  
- **GPT-4o-mini**: ~$0.001 per query  

**Total**: ~$15-30/month for moderate use

---

## 🎊 You're Done!

You now have:
- ✅ Voice AI accessible from your phone  
- ✅ Remembers all your conversations  
- ✅ Works anywhere with internet  
- ✅ Professional UI  
- ✅ Installable as an app  

**Your conductor agent is live! 🚀**

Need help? Check the Render logs or update your OpenAI API key in the dashboard.
