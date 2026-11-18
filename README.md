# Canva to Website

Turn a Canva design into a website you can put online yourself. Fonts, images, animated stickers, videos and links all come with it, and once it's converted it doesn't rely on Canva at all.

Started from [popovycj/CanvaToHTML](https://github.com/popovycj/CanvaToHTML), since rewritten.

## What you need

- A Mac or Windows computer
- [Google Chrome](https://www.google.com/chrome/)
- [Python](https://www.python.org/downloads/) (version 3.11 or newer). On Windows, tick **"Add Python to PATH"** when installing.
- A Canva account that can open the design

## One-time setup

1. Download this project. On GitHub, click the green **Code** button, then **Download ZIP**, and unzip it somewhere easy to find, like your Desktop.
2. Open a terminal:
   - **Mac:** open the **Terminal** app
   - **Windows:** open **Command Prompt**
3. Go into the project folder. Type `cd ` (with a space after it), drag the unzipped folder into the window, and press Enter.
4. Install the converter by copying in these lines.

   **Mac:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install .
   ```

   **Windows:**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install .
   ```

## Let the converter use your Canva login

The converter opens your design the same way you would, so it needs your Canva login. You give it this by saving your Canva "cookies" to a file.

1. Install the **Cookie-Editor** extension in Chrome.
2. Go to [canva.com](https://www.canva.com) and make sure you're logged in.
3. Click the Cookie-Editor icon, change the Export Format to **JSON**, then click on **Export**. This copies your cookies.
4. Make a new text file in the project folder called `cookies.json`, paste in what you copied, and save it.

If you already have a `cookies.txt` file from a different cookie extension, that works too: use its name instead of `cookies.json` below.

Keep this file to yourself. Anyone who has it can get into your Canva account. If your login expires, export it again.

## Convert a design

1. Open your design in Canva and copy the link from Chrome's address bar.
2. In the terminal, inside the project folder, run this (paste your own link between the quotes):
   ```bash
   canva-to-website --cookies cookies.json --url "https://www.canva.com/design/..."
   ```
   If you've closed the terminal since setup, first go back into the folder (step 3 of setup) and run the `activate` line again.
3. A Chrome window opens and loads your design by itself. Leave it alone until the terminal says `Wrote ...`. It takes about a minute, longer if your design has videos.

Your website ends up in the `output` folder, in a folder named after your design (for example `output/my-portfolio/`). Double-click `index.html` inside it to preview it in your browser.

If you convert the same design again, its folder is replaced, so any changes you made to it by hand are lost.

## Put it online

Upload the whole design folder (the one with `index.html` and `assets` inside it) to a free hosting service. The easiest is [Netlify Drop](https://app.netlify.com/drop): drag the folder onto the page and it gives you a link. Cloudflare Pages and GitHub Pages also work.

## Videos

Videos are shrunk to under 24 MB each so they'll upload to any of those services. You can change this by adding these to the end of the convert command:

- `--max-video-mb 95` allows bigger, better-looking videos (fine for Netlify or GitHub Pages, too big for Cloudflare Pages)
- `--max-video-mb 0` keeps videos as they are
- `--video-quality 1080` downloads videos in higher quality before shrinking (the default is 720)

## Good to know

- On phones the whole design shrinks to fit the screen rather than rearranging, so text can be small.
- Links you add in Canva work on the website. A button linked to another page of your design scrolls down to it, and web and email links open as normal. Email and web addresses typed into your text become clickable too.
- Your fonts are copied into the website. Free fonts are fine; if you used Canva Pro fonts, check you're allowed to use them on your own site.
- If Canva changes how its editor works, the converter may stop working until it's updated.

## If something goes wrong

- **"The file 'cookies.json' was not found":** the file isn't in the project folder, or it has a different name. Check it's called exactly `cookies.json`.
- **"The design didn't load":** your cookies have probably expired, or the link is wrong. Export your cookies again.
- **"command not found" or "pip is not recognized":** go back to the project folder and run the `activate` line from setup again.

## Contributing

Use Python 3.11 or newer, in a virtual environment so the project's packages stay separate from the rest of your system. Then install it in editable mode with the test tools, and run the tests:

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

Editable mode (`-e`) means changes you make to the code take effect straight away, without reinstalling.

The tests run against a fake Canva editor page (`tests/fixtures/editor.html`) that copies the parts of Canva the converter relies on, so they don't need a Canva account. Canva changes its editor now and then; to check the converter still works with the real thing, point the live test at one of your designs:

```bash
CANVA_COOKIES=cookies.json CANVA_URL="https://www.canva.com/design/..." pytest -m live
```

If that fails after a Canva update, update the fake editor page to match what Canva does now, then fix the code until both pass.

How the code is laid out, in the order a conversion runs:

| File | Does |
|---|---|
| `cli.py` | Command-line options |
| `browser.py`, `cookies.py` | Starts Chrome and logs it into Canva |
| `editor.py` | Loads the design and reads each page out of the editor |
| `design_data.py` | Reads the design data Canva embeds in the page (links, sections, media) |
| `media.py`, `video.py` | Animated stickers and videos |
| `images.py`, `fonts.py`, `css.py` | Saves images and fonts, keeps only the CSS the design uses |
| `links.py` | Makes links work |
| `site.py` | Writes `index.html` and `assets/` |
| `converter.py` | Runs all of the above in order |

## License

MIT
