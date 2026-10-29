![alt text](https://github.com/FerretPaws/WalltakerPopOutViewer/blob/main/readmeresources/v2%20img.PNG)

# WalltakerPopOutViewer V2.0
A Walltaker desktop client that keeps your images/videos in view, it can pop them out into their own floating window, and shows you the moment something new arrives! V2.0 now handles GIFs, videos, and images!

## What it does

**GIFs & videos (new in 2.0)**
- Plays GIFs, MP4, WebM, MOV and M4V. It's off by default, so turn on *Enable GIFs & videos* under Behaviour.
- GIFs loop until something new is sent.
- Videos can start by themselves the moment they arrive (*Autoplay*) or wait for you, showing the first frame.
- Videos play with sound. Use *Mute videos* and the *Video volume* slider to control it. The volume is remembered next time.
- Click the video to pause or resume it. A little badge shows what it's doing: ❚❚ when paused, ▶ when it starts, ↻ when it's finished (click to replay). The toolbar's Play/Pause button follows along.
- Videos and GIFs work in the pop-out window as well.
- Volume slider for videos.

**Pop-out window**
- Pop the picture out into its own always-on-top window. You can drag it anywhere and set how big you'd like it.
- Fade it out after 10 seconds so it's less in the way. You choose how faded it gets.
- It stays visible when the main window is minimized to the system tray.

**Live updates**
- Connects to the new fork, Walltaker Lycraon, so new images show up instantly with no polling. It reconnects on its own if the connection drops.
- Prefer a different server? Pick *Custom…*, enter any host, and choose live or polling mode.
- You get a notification sound when something new arrives, with its own volume slider.
- Shows who set your wallpaper: their name, whether they're online, whether they're your friend, and how many links they've set. It also has clickable links to their profile and to the original image.

**Replying**
- Send a quick emoji reaction (😍 🤮 👍) or write a custom message along with the reaction.
- The 💦 *I came!~* button sends an orgasm to the person who set your latest wallpaper. You can add an optional message or leave it blank for a default message. This will add an oragsm to that user's profile and cannot be undone.
- Has a preview to show your own sent messages.

**Saving**
- One-click Download for whatever's on screen. GIFs and videos are saved in their own format.
- Optional auto-download saves everything that comes in. Files go to `downloads` next to the exe.

**Look & feel**
- A redesigned layout: a big image viewport, a toolbar on top, and a collapsible *Properties* panel on the right that you can dock or drag away to float. (See GIF below!)
- Three themes: Dark, Light and Classic (e621 colors).
- A custom title bar with window snapping. Drag to the left or right edge for a half-screen window, or to the top to maximise. Drag it back out to restore the old size.

**Under the hood**
- Lower memory use. Very large images are shrunk on load, and old images are released straight away.
- Settings are saved automatically as you change them.
- Run several links at once by putting a copy of the exe in separate folders. Each keeps its own settings.

![alt text](https://github.com/FerretPaws/WalltakerPopOutViewer/blob/main/readmeresources/FloatingProperties.gif)