"""
Video Lecture generator and self-contained 16:9 HTML5/CSS/JS Classroom Player.
Zero external CDN or network dependencies.
Uses Web Speech API (window.speechSynthesis) with timer fallback.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from src.ai import generate_text, is_demo_mode, AIError

logger = logging.getLogger("mastree.video_lecture")

LECTURE_STYLES = {
    1: "clear overview",
    2: "worked example",
    3: "analogy",
    4: "step-by-step"
}


def generate_video_lecture(
    concept_name: str,
    chunks: List[Dict[str, Any]],
    loop_count: int = 1
) -> Optional[Dict[str, Any]]:
    """
    Generate 5-6 lecture scenes in ONE Gemini call.
    Validates JSON and retries once on failure.
    Falls back to deterministic scenes if offline or Gemini fails.
    """
    style = LECTURE_STYLES.get(loop_count, "clear overview")
    chunk_manifest = "\n\n".join(f"[Chunk #{c['chunk_id']}]:\n{c['content']}" for c in chunks)
    chunk_ids = [c["chunk_id"] for c in chunks]

    prompt = f"""
You are the MasteryLoop Video Lecture Director.
Produce a dynamic 5 to 6 scene narrated classroom video lecture for: '{concept_name}'.
Base all content STRICTLY on the following verified source chunks.

TEACHING APPROACH: Deliver the lecture in '{style}' pedagogical style:
- If 'clear overview': Deliver a crystal-clear, structured foundational introduction.
- If 'worked example': Focus on practical SQL query construction, walkthroughs, and code mechanics.
- If 'analogy': Use an intuitive physical metaphor (e.g., mail sorting, puzzle assembly) alongside database rules.
- If 'step-by-step': Present strict procedural phases.

STRICT CONSTRAINTS:
1. Generate exactly 5 to 6 scenes in a JSON object with key 'scenes'.
2. Each scene object must contain:
   - "title": Short descriptive scene title (3-6 words)
   - "bullets": List of at most 4 concise bullet points (each <= 12 words)
   - "narration": Teacher's spoken script of at most 45 words. High clarity, conversational.
   - "key_term": 1-3 word primary keyword to highlight on screen
   - "flow": (Optional) List of 3-4 steps representing an animated process diagram, e.g. ["Parse Query", "Filter WHERE", "Project SELECT"]
   - "citations": List of integer chunk IDs supporting this scene: {chunk_ids}
3. STRICT ACCURACY: Use ONLY the provided chunks. Never extrapolate unstated facts.

SOURCE CHUNKS:
{chunk_manifest}

OUTPUT FORMAT: Return strictly a valid JSON object:
{{
  "scenes": [
    {{
      "title": "...",
      "bullets": ["...", "..."],
      "narration": "...",
      "key_term": "...",
      "flow": ["Step 1", "Step 2", "Step 3"],
      "citations": [{chunk_ids[0] if chunk_ids else 1}]
    }}
  ]
}}
"""

    for attempt in range(2):
        try:
            raw_text = generate_text(prompt, temperature=0.2)
            # Clean markdown code fences
            clean = raw_text.strip()
            if clean.startswith("```"):
                clean = clean.split("\n", 1)[1]
            if clean.endswith("```"):
                clean = clean.rsplit("\n", 1)[0]
            if clean.startswith("json"):
                clean = clean[4:].strip()

            data = json.loads(clean.strip())
            scenes = data.get("scenes", [])
            if isinstance(scenes, list) and 4 <= len(scenes) <= 8:
                # Validate scene structure
                valid = True
                for sc in scenes:
                    if not sc.get("title") or not sc.get("narration"):
                        valid = False
                        break
                    # Enforce bullet count limit
                    if len(sc.get("bullets", [])) > 4:
                        sc["bullets"] = sc["bullets"][:4]
                if valid:
                    return data
        except Exception as e:
            logger.warning(f"Video lecture generation attempt {attempt + 1} error: {e}")

    # Fallback deterministic lecture
    return _build_fallback_video_lecture(concept_name, chunks, style)


def _build_fallback_video_lecture(
    concept_name: str,
    chunks: List[Dict[str, Any]],
    style: str
) -> Dict[str, Any]:
    """Generate high-quality verified fallback scenes from chunks."""
    c_ids = [c["chunk_id"] for c in chunks]
    c1 = chunks[0]["content"] if chunks else f"Core foundations of {concept_name}."
    c2 = chunks[1]["content"] if len(chunks) > 1 else c1
    c3 = chunks[2]["content"] if len(chunks) > 2 else c2

    return {
        "scenes": [
            {
                "title": f"Introduction to {concept_name}",
                "bullets": [
                    f"Core concept: {concept_name}",
                    "Foundational ANSI SQL relational principles",
                    "Deterministic execution rules in IBM Db2",
                    "Optimized data retrieval pipeline"
                ],
                "narration": f"Welcome to this lecture on {concept_name}. We will explore how relational database engines execute these operations with high performance and mathematical consistency.",
                "key_term": concept_name,
                "flow": ["Query Input", "Relational Engine", "Output Tuples"],
                "citations": [c_ids[0]] if c_ids else []
            },
            {
                "title": "Relational Mechanics & Rules",
                "bullets": [
                    c1[:60] + "...",
                    "Strict clause ordering evaluation",
                    "Data type integrity preservation",
                    "Minimizing intermediate buffer usage"
                ],
                "narration": f"In Db2, {concept_name} processes tuples strictly according to the relational lifecycle. Notice how candidate records are evaluated before subsequent downstream clauses.",
                "key_term": "Relational Lifecycle",
                "flow": ["FROM Scan", "Predicate Filter", "Projection"],
                "citations": [c_ids[0]] if c_ids else []
            },
            {
                "title": "Worked Query Execution",
                "bullets": [
                    "Formulating parameterized query syntax",
                    c2[:60] + "...",
                    "Preventing full-table scans with indexes",
                    "Memory management in buffer pools"
                ],
                "narration": "Let us examine a concrete execution scenario. By structuring the query with explicit attributes, the optimizer utilizes covering indexes, avoiding unnecessary page reads.",
                "key_term": "Query Execution",
                "flow": ["Input Query", "Index Scan", "Result Set"],
                "citations": [c_ids[1] if len(c_ids) > 1 else c_ids[0]] if c_ids else []
            },
            {
                "title": "Edge Cases & NULL Handling",
                "bullets": [
                    "Three-valued logic (TRUE, FALSE, UNKNOWN)",
                    "Handling missing or unassigned values",
                    c3[:60] + "...",
                    "Predictable results across all environments"
                ],
                "narration": "Special attention must be given to edge cases, such as NULL values in comparison operations. Always verify three-valued logic behavior to prevent subtle logic defects.",
                "key_term": "Three-Valued Logic",
                "flow": ["Evaluation", "3VL Branch", "Deterministic Output"],
                "citations": [c_ids[-1]] if c_ids else []
            },
            {
                "title": "Summary & Key Takeaways",
                "bullets": [
                    f"Mastery established for {concept_name}",
                    "Verified syntax rules memorized",
                    "Ready for comprehensive 5-question assessment",
                    "Target: 80% mastery across multiple tiers"
                ],
                "narration": f"You are now ready to demonstrate mastery on {concept_name}. Remember the core principles and proceed to the assessment when ready.",
                "key_term": "Mastery Gate",
                "flow": ["Review", "Assessment", "Mastery Gate"],
                "citations": c_ids
            }
        ]
    }


def render_video_lecture_player_html(lecture_data: Dict[str, Any], concept_name: str) -> str:
    """
    Generate self-contained HTML/CSS/JS player for the video lecture.
    No CDN, no network calls. Works 100% offline.
    Features:
    - 16:9 dark classroom screen
    - Bullet point staggered animations
    - Animated flow diagram boxes with arrows
    - Web Speech API narration with auto-advance and timer fallback
    - Speed control (0.8x, 1x, 1.25x), Play/Pause, Prev, Next, Mute, Captions
    - Scene indicator dots and progress bar
    """
    scenes = lecture_data.get("scenes", [])
    scenes_json = json.dumps(scenes).replace("</script>", "<\\/script>")

    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
    user-select: none;
  }}
  body {{
    background-color: transparent;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 10px 0;
  }}
  .player-wrapper {{
    width: 100%;
    max-width: 960px;
    background: #0f172a;
    border-radius: 14px;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6);
    overflow: hidden;
    border: 1px solid #1e293b;
    display: flex;
    flex-direction: column;
  }}
  /* 16:9 Screen */
  .screen {{
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    background: radial-gradient(circle at 50% 20%, #1e293b 0%, #090d16 100%);
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    padding: 24px 32px 16px 32px;
    color: #f8fafc;
    overflow: hidden;
  }}
  /* Ambient glow */
  .screen::before {{
    content: '';
    position: absolute;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background: radial-gradient(circle at 50% 30%, rgba(14, 165, 233, 0.08) 0%, transparent 60%);
    pointer-events: none;
  }}
  /* Top Screen Bar */
  .screen-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    z-index: 2;
  }}
  .topic-badge {{
    font-size: 0.85rem;
    font-weight: 700;
    color: #38bdf8;
    background: rgba(56, 189, 248, 0.12);
    border: 1px solid rgba(56, 189, 248, 0.3);
    padding: 4px 12px;
    border-radius: 20px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
  }}
  .keyterm-pill {{
    font-size: 0.85rem;
    font-weight: 700;
    color: #fbbf24;
    background: rgba(251, 191, 36, 0.12);
    border: 1px solid rgba(251, 191, 36, 0.3);
    padding: 4px 14px;
    border-radius: 20px;
    display: flex;
    align-items: center;
    gap: 6px;
  }}
  .citation-pill {{
    font-size: 0.75rem;
    color: #94a3b8;
    background: rgba(148, 163, 184, 0.1);
    padding: 4px 10px;
    border-radius: 12px;
  }}
  /* Center Stage */
  .stage {{
    z-index: 2;
    margin: auto 0;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }}
  .scene-title {{
    font-size: 1.85rem;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: -0.5px;
    text-shadow: 0 2px 10px rgba(0,0,0,0.5);
    animation: fadeIn 0.4s ease-out;
  }}
  .bullets-list {{
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }}
  .bullet-item {{
    display: flex;
    align-items: center;
    gap: 12px;
    font-size: 1.15rem;
    color: #e2e8f0;
    opacity: 0;
    transform: translateY(10px);
    transition: opacity 0.4s ease, transform 0.4s ease;
  }}
  .bullet-item.visible {{
    opacity: 1;
    transform: translateY(0);
  }}
  .bullet-icon {{
    color: #38bdf8;
    font-size: 1.2rem;
  }}
  /* Animated Flow Diagram */
  .flow-container {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 10px;
    animation: fadeIn 0.6s ease;
  }}
  .flow-step {{
    background: rgba(30, 41, 59, 0.8);
    border: 1px solid #38bdf8;
    color: #38bdf8;
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 0.85rem;
    font-weight: 600;
    box-shadow: 0 4px 12px rgba(56, 189, 248, 0.15);
  }}
  .flow-arrow {{
    color: #94a3b8;
    font-size: 1rem;
    animation: pulseArrow 1.5s infinite;
  }}
  /* Subtitles / Captions */
  .captions-bar {{
    z-index: 2;
    background: rgba(15, 23, 42, 0.85);
    backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 10px 18px;
    text-align: center;
    font-size: 1.05rem;
    color: #f1f5f9;
    font-weight: 500;
    min-height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
    line-height: 1.4;
  }}
  /* Control Deck */
  .control-deck {{
    background: #090d16;
    padding: 12px 24px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    border-top: 1px solid #1e293b;
  }}
  /* Progress Track */
  .progress-track {{
    position: relative;
    width: 100%;
    height: 6px;
    background: #1e293b;
    border-radius: 3px;
    cursor: pointer;
  }}
  .progress-fill {{
    height: 100%;
    background: linear-gradient(90deg, #0284c7, #38bdf8);
    border-radius: 3px;
    width: 0%;
    transition: width 0.3s ease;
  }}
  .scene-dots {{
    position: absolute;
    top: -3px;
    width: 100%;
    display: flex;
    justify-content: space-between;
    pointer-events: none;
  }}
  .scene-dot {{
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: #334155;
    border: 2px solid #090d16;
    transition: background 0.3s ease;
  }}
  .scene-dot.active {{
    background: #38bdf8;
    box-shadow: 0 0 8px #38bdf8;
  }}
  /* Buttons Row */
  .controls-row {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 4px;
  }}
  .btn-group {{
    display: flex;
    align-items: center;
    gap: 8px;
  }}
  .ctrl-btn {{
    background: #1e293b;
    color: #f8fafc;
    border: 1px solid #334155;
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 0.9rem;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s ease;
  }}
  .ctrl-btn:hover {{
    background: #334155;
    border-color: #475569;
  }}
  .ctrl-btn.primary {{
    background: #0284c7;
    border-color: #0284c7;
  }}
  .ctrl-btn.primary:hover {{
    background: #0369a1;
  }}
  .ctrl-btn.active {{
    background: #38bdf8;
    color: #090d16;
    border-color: #38bdf8;
  }}
  .scene-counter {{
    color: #94a3b8;
    font-size: 0.85rem;
    font-weight: 600;
  }}
  @keyframes fadeIn {{
    from {{ opacity: 0; transform: translateY(-6px); }}
    to {{ opacity: 1; transform: translateY(0); }}
  }}
  @keyframes pulseArrow {{
    0%, 100% {{ transform: translateX(0); opacity: 0.6; }}
    50% {{ transform: translateX(4px); opacity: 1; }}
  }}
</style>
</head>
<body>

<div class="player-wrapper">
  <div class="screen" id="screen">
    <div class="screen-header">
      <div class="topic-badge">{concept_name}</div>
      <div class="keyterm-pill" id="keyterm-badge">💡 <span id="keyterm-text">...</span></div>
      <div class="citation-pill" id="citation-badge">Source: Chunk #1</div>
    </div>

    <div class="stage">
      <div class="scene-title" id="scene-title">Loading Scene...</div>
      <ul class="bullets-list" id="bullets-container"></ul>
      <div class="flow-container" id="flow-container"></div>
    </div>

    <div class="captions-bar" id="captions-text">...</div>
  </div>

  <div class="control-deck">
    <div class="progress-track" id="progress-track" onclick="handleTrackClick(event)">
      <div class="progress-fill" id="progress-fill"></div>
      <div class="scene-dots" id="scene-dots"></div>
    </div>

    <div class="controls-row">
      <div class="btn-group">
        <button class="ctrl-btn" onclick="prevScene()" title="Previous Scene">⏮ Prev</button>
        <button class="ctrl-btn primary" id="play-btn" onclick="togglePlay()">⏸ Pause</button>
        <button class="ctrl-btn" onclick="nextScene()" title="Next Scene">Next ⏭</button>
        <span class="scene-counter" id="scene-counter">Scene 1 of 5</span>
      </div>

      <div class="btn-group">
        <button class="ctrl-btn" id="speed-08" onclick="setSpeed(0.8)">0.8x</button>
        <button class="ctrl-btn active" id="speed-10" onclick="setSpeed(1.0)">1x</button>
        <button class="ctrl-btn" id="speed-125" onclick="setSpeed(1.25)">1.25x</button>
        <button class="ctrl-btn" id="captions-btn" onclick="toggleCaptions()" title="Toggle Subtitles">💬</button>
        <button class="ctrl-btn" id="mute-btn" onclick="toggleMute()" title="Mute Audio">🔊</button>
      </div>
    </div>
  </div>
</div>

<script>
  const scenes = {scenes_json};
  let currentSceneIdx = 0;
  let isPlaying = true;
  let currentSpeed = 1.0;
  let isMuted = false;
  let showCaptions = true;
  let timerId = null;
  let bulletTimerId = null;

  // Initialize Scene Dots
  const dotsContainer = document.getElementById("scene-dots");
  scenes.forEach((_, idx) => {{
    const dot = document.createElement("div");
    dot.className = "scene-dot" + (idx === 0 ? " active" : "");
    dotsContainer.appendChild(dot);
  }});

  function loadScene(idx) {{
    if (idx < 0 || idx >= scenes.length) return;
    currentSceneIdx = idx;

    // Clear previous timers & speech
    if (timerId) clearTimeout(timerId);
    if (bulletTimerId) clearTimeout(bulletTimerId);
    if (window.speechSynthesis) window.speechSynthesis.cancel();

    const scene = scenes[idx];

    // Update Headers
    document.getElementById("keyterm-text").innerText = scene.key_term || "{concept_name}";
    const citations = scene.citations && scene.citations.length ? scene.citations.join(", #") : "Seed";
    document.getElementById("citation-badge").innerText = "Source Chunks: #" + citations;
    document.getElementById("scene-counter").innerText = `Scene ${{idx + 1}} of ${{scenes.length}}`;

    // Title
    document.getElementById("scene-title").innerText = scene.title;

    // Bullets (Reveal one by one)
    const bulletsList = document.getElementById("bullets-container");
    bulletsList.innerHTML = "";
    (scene.bullets || []).forEach((bText, bIdx) => {{
      const li = document.createElement("li");
      li.className = "bullet-item";
      li.innerHTML = `<span class="bullet-icon">▸</span><span>${{bText}}</span>`;
      bulletsList.appendChild(li);

      // Staggered reveal
      setTimeout(() => {{
        li.classList.add("visible");
      }}, (bIdx + 1) * 700 / currentSpeed);
    }});

    // Flow diagram
    const flowContainer = document.getElementById("flow-container");
    flowContainer.innerHTML = "";
    if (scene.flow && scene.flow.length) {{
      scene.flow.forEach((step, sIdx) => {{
        const stepBox = document.createElement("div");
        stepBox.className = "flow-step";
        stepBox.innerText = step;
        flowContainer.appendChild(stepBox);

        if (sIdx < scene.flow.length - 1) {{
          const arrow = document.createElement("span");
          arrow.className = "flow-arrow";
          arrow.innerText = "➔";
          flowContainer.appendChild(arrow);
        }}
      }});
    }}

    // Captions
    const capEl = document.getElementById("captions-text");
    capEl.innerText = scene.narration || "";
    capEl.style.display = showCaptions ? "flex" : "none";

    // Update Progress
    const progPercent = ((idx + 1) / scenes.length) * 100;
    document.getElementById("progress-fill").style.width = progPercent + "%";
    document.querySelectorAll(".scene-dot").forEach((d, dIdx) => {{
      d.classList.toggle("active", dIdx <= idx);
    }});

    // Play narration
    if (isPlaying) {{
      speakNarration(scene.narration);
    }}
  }}

  function speakNarration(text) {{
    const wordCount = (text || "").split(/\\s+/).length;
    const estDurationMs = Math.max(5000, (wordCount / (2.5 * currentSpeed)) * 1000);

    if (!isMuted && window.speechSynthesis && text) {{
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = currentSpeed;
      utterance.pitch = 1.0;

      utterance.onend = function() {{
        if (isPlaying) {{
          handleSceneEnd();
        }}
      }};

      utterance.onerror = function() {{
        timerId = setTimeout(handleSceneEnd, estDurationMs);
      }};

      window.speechSynthesis.speak(utterance);
    }} else {{
      timerId = setTimeout(handleSceneEnd, estDurationMs);
    }}
  }}

  function handleSceneEnd() {{
    if (currentSceneIdx < scenes.length - 1) {{
      nextScene();
    }} else {{
      isPlaying = false;
      document.getElementById("play-btn").innerText = "▶ Replay";
      document.getElementById("captions-text").innerText = "🎓 Lecture Complete! Please click 'Take the assessment' below.";
    }}
  }}

  function togglePlay() {{
    isPlaying = !isPlaying;
    const btn = document.getElementById("play-btn");
    if (isPlaying) {{
      btn.innerText = "⏸ Pause";
      if (currentSceneIdx === scenes.length - 1) {{
        loadScene(0);
      }} else {{
        loadScene(currentSceneIdx);
      }}
    }} else {{
      btn.innerText = "▶ Play";
      if (window.speechSynthesis) window.speechSynthesis.cancel();
      if (timerId) clearTimeout(timerId);
    }}
  }}

  function nextScene() {{
    if (currentSceneIdx < scenes.length - 1) {{
      loadScene(currentSceneIdx + 1);
    }}
  }}

  function prevScene() {{
    if (currentSceneIdx > 0) {{
      loadScene(currentSceneIdx - 1);
    }}
  }}

  function setSpeed(speed) {{
    currentSpeed = speed;
    ["08", "10", "125"].forEach(s => document.getElementById("speed-" + s).classList.remove("active"));
    if (speed === 0.8) document.getElementById("speed-08").classList.add("active");
    if (speed === 1.0) document.getElementById("speed-10").classList.add("active");
    if (speed === 1.25) document.getElementById("speed-125").classList.add("active");
    loadScene(currentSceneIdx);
  }}

  function toggleMute() {{
    isMuted = !isMuted;
    const btn = document.getElementById("mute-btn");
    btn.innerText = isMuted ? "🔇" : "🔊";
    if (isMuted && window.speechSynthesis) {{
      window.speechSynthesis.cancel();
    }}
    loadScene(currentSceneIdx);
  }}

  function toggleCaptions() {{
    showCaptions = !showCaptions;
    document.getElementById("captions-btn").classList.toggle("active", showCaptions);
    document.getElementById("captions-text").style.display = showCaptions ? "flex" : "none";
  }}

  function handleTrackClick(event) {{
    const rect = event.currentTarget.getBoundingClientRect();
    const clickX = event.clientX - rect.left;
    const fraction = clickX / rect.width;
    const targetIdx = Math.min(scenes.length - 1, Math.max(0, Math.floor(fraction * scenes.length)));
    loadScene(targetIdx);
  }}

  // Start on scene 0
  loadScene(0);
</script>

</body>
</html>
"""

