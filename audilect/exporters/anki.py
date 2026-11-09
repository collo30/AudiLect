import csv
import io
from typing import List, Dict, Any


def export_anki_csv(
    topic_blocks: List[Dict[str, Any]],
    concept_anchors: List[Dict[str, Any]],
    checkpoints: List[Dict[str, Any]],
    deck_name: str = "Audilect::Lecture"
) -> str:
    """
    Exports lecture active recall prompts and concept micro-primers as Anki flashcards.
    Supports both Cloze deletion cards ({{c1::...}}) and Cue-Response cards.
    
    Returns:
        String content formatted for direct Anki import.
    """
    output = io.StringIO()
    # Anki file headers
    output.write(f"#separator:Tab\n")
    output.write(f"#html:true\n")
    output.write(f"#deck:{deck_name}\n")
    output.write(f"#tags:audilect active_recall lecture\n\n")

    writer = csv.writer(output, delimiter='\t')

    # 1. Export Concept Anchors as Cloze deletions
    for anchor in concept_anchors:
        term = anchor.get("term", "")
        primer = anchor.get("primer", "")
        cue = anchor.get("cue", f"Define {term} in this lecture context.")
        timestamp = anchor.get("timestamp", 0.0)
        time_tag = f"[{int(timestamp//60):02d}:{int(timestamp%60):02d}]"

        # Create cloze prompt
        front_cloze = f"<b>{cue}</b><br><br>Context {time_tag}: {primer.replace(term, '{{c1::' + term + '}}')}"
        back_extra = f"<b>Key Concept:</b> {term}<br><b>Timestamp:</b> {time_tag}"
        tags = f"audilect_concept slide_{anchor.get('slide_id', 1)}"

        writer.writerow([front_cloze, back_extra, tags])

    # 2. Export Socratic Checkpoints as Question / Answer flashcards
    for chk in checkpoints:
        q_text = chk.get("question", "")
        explanation = chk.get("explanation", "")
        opts = chk.get("options", [])
        c_idx = chk.get("correct_index", 0)
        correct_ans = opts[c_idx] if c_idx < len(opts) else "Correct Concept"
        timestamp = chk.get("timestamp", 0.0)
        time_tag = f"[{int(timestamp//60):02d}:{int(timestamp%60):02d}]"

        front = f"<b>[Socratic Checkpoint {time_tag}]</b><br>{q_text}<br><br><i>Formulate the underlying reasoning before flipping.</i>"
        back = f"<b>Correct Answer:</b><br>{correct_ans}<br><br><b>Cognitive Rationale:</b><br>{explanation}"
        tags = f"audilect_checkpoint topic_{chk.get('topic_id', 1)}"

        writer.writerow([front, back, tags])

    return output.getvalue()
