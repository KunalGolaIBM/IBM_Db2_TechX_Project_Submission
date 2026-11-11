"""
Generate visual screenshot illustrations for docs/screenshots/
Creates clean, polished UI presentation cards representing the 4 core views of MasteryLoop.
"""

import os
from PIL import Image, ImageDraw, ImageFont

SCREENSHOTS_DIR = os.path.join(os.path.dirname(__file__), "..", "docs", "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)


def get_font(size: int, bold: bool = False):
    """Load default or standard font."""
    try:
        # Standard Windows fonts
        font_name = "arialbd.ttf" if bold else "arial.ttf"
        return ImageFont.truetype(font_name, size)
    except Exception:
        try:
            font_name = "segoeuib.ttf" if bold else "segoeui.ttf"
            return ImageFont.truetype(font_name, size)
        except Exception:
            return ImageFont.load_default()


def create_header(draw, title: str, subtitle: str, width: int = 1000):
    """Draw top application navbar/header."""
    draw.rectangle([0, 0, width, 70], fill="#0f62fe")
    draw.text((30, 15), "🎓 MasteryLoop — Adaptive SQL Learning Engine", fill="#ffffff", font=get_font(20, True))
    draw.text((30, 42), "Connected to IBM Db2 LUW (MLOOP) • Student: alex_sql", fill="#d0e2ff", font=get_font(12))


def generate_board_screenshot():
    """Generate Step-by-Step Lesson Board view."""
    width, height = 1000, 600
    img = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(img)

    create_header(draw, "MasteryLoop", "")

    # Tabs
    draw.rectangle([0, 70, width, 110], fill="#f4f4f4")
    draw.rectangle([30, 75, 180, 110], fill="#ffffff")
    draw.text((45, 85), "📖 Lesson Board", fill="#0f62fe", font=get_font(14, True))
    draw.text((210, 85), "📝 Concept Quiz & Gate", fill="#525252", font=get_font(14))
    draw.text((400, 85), "📊 Student Progress", fill="#525252", font=get_font(14))
    draw.text((580, 85), "✍️ Notes & Ingestion", fill="#525252", font=get_font(14))

    # Active concept banner
    draw.text((30, 130), "Lesson Board: SELECT basics", fill="#161616", font=get_font(22, True))
    draw.text((30, 160), "Foundational attribute projection and DISTINCT • Loop #1 (Step-by-Step Style)", fill="#6f6f6f", font=get_font(13))

    # Progress bar
    draw.rectangle([30, 190, 970, 202], fill="#e0e0e0")
    draw.rectangle([30, 190, 650, 202], fill="#0f62fe")
    draw.text((30, 208), "Step 2 of 3 (66% Completed)", fill="#0f62fe", font=get_font(12, True))

    # Card 1
    draw.rounded_rectangle([30, 235, 970, 345], radius=8, fill="#1e293b", outline="#38bdf8", width=2)
    draw.rectangle([30, 235, 38, 345], fill="#38bdf8")
    draw.text((55, 248), "Step 1: Foundational Projection & Schema Stability", fill="#38bdf8", font=get_font(16, True))
    draw.rounded_rectangle([780, 245, 950, 270], radius=12, fill="#0f172a")
    draw.text((795, 250), "Source Chunks: #1, #2", fill="#38bdf8", font=get_font(11, True))
    
    body1 = "The SELECT statement projectively selects attributes and computes expressions from target relations.\nExplicit column enumeration preserves query maintainability and prevents unwanted memory overhead."
    draw.text((55, 280), body1, fill="#f1f5f9", font=get_font(13))

    # Card 2
    draw.rounded_rectangle([30, 365, 970, 485], radius=8, fill="#1e293b", outline="#38bdf8", width=2)
    draw.rectangle([30, 365, 38, 485], fill="#38bdf8")
    draw.text((55, 378), "Step 2: Expressions, Aliases, and Duplicate Filtering (DISTINCT)", fill="#38bdf8", font=get_font(16, True))
    draw.rounded_rectangle([780, 375, 950, 400], radius=12, fill="#0f172a")
    draw.text((795, 380), "Source Chunks: #2", fill="#38bdf8", font=get_font(11, True))
    
    body2 = "Column alias designations using the optional AS keyword rename output headers seamlessly.\nTo enforce duplicate row elimination, SQL provides the DISTINCT keyword directly preceding column definitions."
    draw.text((55, 410), body2, fill="#f1f5f9", font=get_font(13))

    # Buttons
    draw.rounded_rectangle([30, 515, 200, 555], radius=6, fill="#0f62fe")
    draw.text((65, 527), "Next Step ➡️", fill="#ffffff", font=get_font(14, True))

    draw.rounded_rectangle([220, 515, 380, 555], radius=6, fill="#f4f4f4", outline="#8d8d8d")
    draw.text((250, 527), "Restart Board 🔄", fill="#161616", font=get_font(14))

    out_path = os.path.join(SCREENSHOTS_DIR, "board.png")
    img.save(out_path)
    print(f"Saved: {out_path}")


def generate_quiz_screenshot():
    """Generate Concept Quiz and Deterministic Assessment view."""
    width, height = 1000, 600
    img = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(img)

    create_header(draw, "MasteryLoop", "")

    # Tabs
    draw.rectangle([0, 70, width, 110], fill="#f4f4f4")
    draw.text((45, 85), "📖 Lesson Board", fill="#525252", font=get_font(14))
    draw.rectangle([190, 75, 380, 110], fill="#ffffff")
    draw.text((205, 85), "📝 Concept Quiz & Gate", fill="#0f62fe", font=get_font(14, True))
    draw.text((400, 85), "📊 Student Progress", fill="#525252", font=get_font(14))
    draw.text((580, 85), "✍️ Notes & Ingestion", fill="#525252", font=get_font(14))

    # KPI Metrics
    draw.rounded_rectangle([30, 125, 240, 195], radius=8, fill="#f4f4f4")
    draw.text((45, 135), "Mastery Score", fill="#525252", font=get_font(12))
    draw.text((45, 155), "84.2%", fill="#0e6027", font=get_font(24, True))

    draw.rounded_rectangle([260, 125, 470, 195], radius=8, fill="#f4f4f4")
    draw.text((275, 135), "Total Attempts", fill="#525252", font=get_font(12))
    draw.text((275, 155), "6", fill="#161616", font=get_font(24, True))

    draw.rounded_rectangle([490, 125, 700, 195], radius=8, fill="#f4f4f4")
    draw.text((505, 135), "Difficulty Span", fill="#525252", font=get_font(12))
    draw.text((505, 155), "3 / 3 Tiers", fill="#161616", font=get_font(24, True))

    draw.rounded_rectangle([720, 125, 970, 195], radius=8, fill="#defbe6")
    draw.text((740, 135), "Gate Status", fill="#0e6027", font=get_font(12, True))
    draw.text((740, 155), "PASSED ✅", fill="#0e6027", font=get_font(22, True))

    # Question Card
    draw.rounded_rectangle([30, 215, 970, 480], radius=8, fill="#f9fafb", outline="#e0e0e0")
    draw.text((50, 230), "Question 1  [EASY]  (Source Chunk #1)", fill="#161616", font=get_font(15, True))
    draw.text((50, 255), "What is the primary role of the SELECT clause in SQL relational operations?", fill="#393939", font=get_font(14))

    # Options
    draw.rounded_rectangle([50, 285, 950, 320], radius=6, fill="#ffffff", outline="#d1d5db")
    draw.text((70, 295), "A) To physically delete records from primary storage", fill="#374151", font=get_font(13))

    draw.rounded_rectangle([50, 330, 950, 365], radius=6, fill="#e0f2fe", outline="#0284c7", width=2)
    draw.text((70, 340), "B) To project attributes and compute expressions from target relations  ✓ Selected", fill="#0369a1", font=get_font(13, True))

    draw.rounded_rectangle([50, 375, 950, 410], radius=6, fill="#ffffff", outline="#d1d5db")
    draw.text((70, 385), "C) To define foreign key cascade constraints", fill="#374151", font=get_font(13))

    draw.rounded_rectangle([50, 420, 950, 455], radius=6, fill="#ffffff", outline="#d1d5db")
    draw.text((70, 430), "D) To enforce autocommit off across database sessions", fill="#374151", font=get_font(13))

    # Submit Button
    draw.rounded_rectangle([30, 505, 360, 550], radius=6, fill="#0f62fe")
    draw.text((55, 520), "Submit Quiz for Deterministic Grading", fill="#ffffff", font=get_font(14, True))

    out_path = os.path.join(SCREENSHOTS_DIR, "quiz.png")
    img.save(out_path)
    print(f"Saved: {out_path}")


def generate_root_cause_screenshot():
    """Generate Db2 Recursive CTE Prerequisite Root Cause Analysis view."""
    width, height = 1000, 600
    img = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(img)

    create_header(draw, "MasteryLoop", "")

    draw.rectangle([0, 70, width, 110], fill="#f4f4f4")
    draw.rectangle([190, 75, 380, 110], fill="#ffffff")
    draw.text((205, 85), "📝 Concept Quiz & Gate", fill="#0f62fe", font=get_font(14, True))

    # Gate Fail Banner
    draw.rounded_rectangle([30, 125, 970, 190], radius=8, fill="#fee2e2", outline="#ef4444")
    draw.text((50, 137), "🛑 GATE NOT PASSED", fill="#991b1b", font=get_font(16, True))
    draw.text((50, 162), "Failed gate: Mastery score 0.42 is below 0.80 threshold. Prerequisite diagnostics activated.", fill="#7f1d1d", font=get_font(13))

    # Root Cause Recommendation Card
    draw.rounded_rectangle([30, 205, 970, 290], radius=8, fill="#fffbeb", outline="#f59e0b", width=2)
    draw.text((50, 217), "🔍 Root Cause Identified by IBM Db2 Prerequisite Graph:", fill="#92400e", font=get_font(15, True))
    draw.text((50, 240), "Your mastery in prerequisite 'WHERE' is only 20.0%. MasteryLoop requires mastering 'WHERE'", fill="#78350f", font=get_font(13))
    draw.text((50, 260), "before attempting complex 'JOINs'. Let's remediate this foundational concept first.", fill="#78350f", font=get_font(13))

    draw.rounded_rectangle([700, 230, 950, 270], radius=6, fill="#d97706")
    draw.text((720, 242), "Remediate 'WHERE' First 🛠️", fill="#ffffff", font=get_font(13, True))

    # Why This Expander
    draw.rounded_rectangle([30, 310, 970, 560], radius=8, fill="#f8fafc", outline="#cbd5e1")
    draw.text((50, 325), "▼ 🌲 Why this Root Cause? (Db2 Recursive CTE Traversal SQL & Result Set)", fill="#0f172a", font=get_font(14, True))

    # Code snippet
    draw.rectangle([50, 350, 950, 450], fill="#1e293b")
    code = (
        "WITH prereq_tree (concept_id, prereq_id, depth) AS (\n"
        "    SELECT cp.concept_id, cp.prereq_id, 1 FROM concept_prereqs cp WHERE cp.concept_id = ?\n"
        "    UNION ALL\n"
        "    SELECT pt.concept_id, cp2.prereq_id, pt.depth + 1 FROM prereq_tree pt, concept_prereqs cp2\n"
        "    WHERE pt.prereq_id = cp2.concept_id\n"
        ")\n"
        "SELECT c.concept_id, c.name, MIN(pt.depth) AS min_depth, COALESCE(m.mastery_score, 0.0) AS score\n"
        "FROM prereq_tree pt JOIN concepts c ON pt.prereq_id = c.concept_id\n"
        "LEFT JOIN mastery m ON m.student_id = ? AND m.concept_id = c.concept_id\n"
        "GROUP BY c.concept_id, c.name, m.mastery_score ORDER BY score ASC, min_depth DESC;"
    )
    draw.text((60, 355), code, fill="#38bdf8", font=get_font(10))

    # Table preview
    draw.rectangle([50, 465, 950, 545], fill="#ffffff", outline="#e2e8f0")
    draw.text((60, 475), "CONCEPT_ID | NAME          | MIN_DEPTH | MASTERY_SCORE | STATUS", fill="#475569", font=get_font(11, True))
    draw.text((60, 498), "2          | WHERE         | 1         | 0.2000        | ❌ WEAKEST ROOT CAUSE", fill="#dc2626", font=get_font(11, True))
    draw.text((60, 520), "1          | SELECT basics | 1         | 0.9200        | ✅ MASTERED", fill="#16a34a", font=get_font(11, True))

    out_path = os.path.join(SCREENSHOTS_DIR, "root_cause.png")
    img.save(out_path)
    print(f"Saved: {out_path}")


def generate_progress_screenshot():
    """Generate Student Progress Matrix & Analytics Line Chart view."""
    width, height = 1000, 600
    img = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(img)

    create_header(draw, "MasteryLoop", "")

    draw.rectangle([0, 70, width, 110], fill="#f4f4f4")
    draw.rectangle([390, 75, 560, 110], fill="#ffffff")
    draw.text((405, 85), "📊 Student Progress", fill="#0f62fe", font=get_font(14, True))

    draw.text((30, 125), "Curriculum Progress Matrix (Powered by SQL VIEW v_student_progress)", fill="#161616", font=get_font(18, True))

    # Matrix Table
    draw.rectangle([30, 155, 970, 310], fill="#ffffff", outline="#d1d5db")
    draw.rectangle([30, 155, 970, 185], fill="#f3f4f6")
    draw.text((45, 162), "SEQ  | CONCEPT NAME          | MASTERY SCORE | ATTEMPTS | DIFFICULTY SPAN | STATUS", fill="#374151", font=get_font(11, True))

    rows = [
        ("1    | SELECT basics         | 92.4%         | 6        | 3 Levels        | ✅ MASTERED", "#15803d"),
        ("2    | WHERE                 | 86.5%         | 5        | 2 Levels        | ✅ MASTERED", "#15803d"),
        ("3    | ORDER BY              | 81.0%         | 5        | 2 Levels        | ✅ MASTERED", "#15803d"),
        ("4    | Aggregate functions   | 54.0%         | 3        | 2 Levels        | ⏳ IN PROGRESS", "#b45309"),
        ("5    | GROUP BY              | 0.0%          | 0        | 0 Levels        | ⏳ NOT STARTED", "#6b7280"),
    ]
    for i, (r_text, col) in enumerate(rows):
        y = 195 + i * 23
        draw.text((45, y), r_text, fill=col, font=get_font(11))

    # Chart Area
    draw.text((30, 330), "📈 Chronological Mastery Trajectory (from table: mastery_history)", fill="#161616", font=get_font(16, True))
    draw.rounded_rectangle([30, 360, 970, 565], radius=8, fill="#fafafa", outline="#e5e7eb")

    # Draw mock chart axes & lines
    draw.line([(80, 520), (920, 520)], fill="#9ca3af", width=2)
    draw.line([(80, 390), (80, 520)], fill="#9ca3af", width=2)
    draw.text((40, 390), "1.0", fill="#6b7280", font=get_font(10))
    draw.text((40, 450), "0.5", fill="#6b7280", font=get_font(10))
    draw.text((40, 515), "0.0", fill="#6b7280", font=get_font(10))

    # Threshold line 0.8
    draw.line([(80, 416), (920, 416)], fill="#ef4444", width=1)
    draw.text((925, 410), "Gate Threshold (0.80)", fill="#ef4444", font=get_font(10, True))

    # Trajectory 1: SELECT basics (Blue)
    pts1 = [(80, 480), (220, 440), (360, 410), (500, 398), (640, 395)]
    draw.line(pts1, fill="#0f62fe", width=3)
    for p in pts1:
        draw.ellipse([p[0]-3, p[1]-3, p[0]+3, p[1]+3], fill="#0f62fe")
    draw.text((650, 390), "SELECT basics", fill="#0f62fe", font=get_font(11, True))

    # Trajectory 2: WHERE (Green)
    pts2 = [(360, 510), (500, 470), (640, 425), (780, 405)]
    draw.line(pts2, fill="#10b981", width=3)
    for p in pts2:
        draw.ellipse([p[0]-3, p[1]-3, p[0]+3, p[1]+3], fill="#10b981")
    draw.text((790, 400), "WHERE", fill="#10b981", font=get_font(11, True))

    out_path = os.path.join(SCREENSHOTS_DIR, "progress.png")
    img.save(out_path)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    generate_board_screenshot()
    generate_quiz_screenshot()
    generate_root_cause_screenshot()
    generate_progress_screenshot()

