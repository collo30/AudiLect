from typing import List, Dict, Any


def export_cornell_markdown(
    title: str,
    duration_str: str,
    topic_blocks: List[Dict[str, Any]],
    concept_anchors: List[Dict[str, Any]],
    checkpoints: List[Dict[str, Any]]
) -> str:
    """
    Generates a high-density Cornell-style structured Markdown document.
    Structure:
      - Lecture Title & Metadata
      - Section 1: Key Spoken Concepts (if present)
      - Section 2: Cornell 2-Column Active Notes (Cue | Notes)
      - Section 3: Active Recall Checkpoints
      - Section 4: Lecture Summary Synthesis (Grounded entirely in spoken content)
    """
    lines = []
    lines.append(f"# {title}")
    lines.append(f"**Duration:** {duration_str} | **Topic Sections:** {len(topic_blocks)}  ")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Section 1: Concept Micro-Primers (only if real concepts exist)
    if concept_anchors:
        lines.append("## 1. Key Concept Anchors")
        lines.append("")
        lines.append("| Concept | Time | Spoken Context | Retrieval Cue |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for a in concept_anchors:
            t = a.get("timestamp", 0.0)
            time_tag = f"`{int(t//60):02d}:{int(t%60):02d}`"
            primer = a.get('primer', '').replace('|', '\\|')
            lines.append(f"| **{a.get('term')}** | {time_tag} | {primer[:120]}... | {a.get('cue')} |")
        lines.append("")

    # Section 2: Cornell Notes (Cue vs Notes)
    lines.append("## 2. Cornell Active Notes")
    lines.append("")
    lines.append("| Cue / Active Prompt | Spoken Lecture Content & Core Insights |")
    lines.append("| :--- | :--- |")

    for block in topic_blocks:
        t_start = block.get("start", 0.0)
        time_tag = f"`{int(t_start//60):02d}:{int(t_start%60):02d}`"
        topic_title = block.get("title", "Section")
        slide_id = block.get("slide_id", "-")

        cue = f"**{topic_title}**<br>*{time_tag} (Slide #{slide_id})*<br><br>• What was the main point?<br>• What evidence was presented?"
        
        # Clean text into bulleted takeaways
        text = block.get("full_text", "")
        sentences = [s.strip().replace('|', '\\|') for s in text.split(".") if len(s.strip()) > 10]
        notes_body = "<br>".join([f"• {s}." for s in sentences[:6]]) or "No notes recorded."
        
        lines.append(f"| {cue} | {notes_body} |")

    lines.append("")

    # Section 3: Active Recall Checkpoints
    if checkpoints:
        lines.append("## 3. Active Recall Checkpoints")
        lines.append("")
        for i, chk in enumerate(checkpoints, 1):
            t = chk.get("timestamp", 0.0)
            time_tag = f"`{int(t//60):02d}:{int(t%60):02d}`"
            lines.append(f"### Checkpoint {i}: {chk.get('question')} ({time_tag})")
            lines.append("")
            opts = chk.get("options", [])
            c_idx = chk.get("correct_index", 0)
            if c_idx < len(opts):
                lines.append(f"- **Core Spoken Takeaway:** {opts[c_idx]}")
            lines.append("")
            lines.append(f"> **Context:** {chk.get('explanation')}")
            lines.append("")

    # Section 4: High-Yield Bottom Summary (Synthesized from actual blocks)
    lines.append("## 4. Lecture Synthesis & Summary")
    lines.append("")
    for i, block in enumerate(topic_blocks[:6], 1):
        sentences = [s.strip() for s in block.get("full_text", "").split(".") if len(s.strip()) > 15]
        if sentences:
            lines.append(f"{i}. **{block.get('title')}:** {sentences[0]}.")
    lines.append("")

    return "\n".join(lines)
