import re
from typing import List, Dict, Any, Optional


def clean_text(text: str) -> str:
    """Removes extra whitespace and normalizes text."""
    return re.sub(r'\s+', ' ', text).strip()


# Common non-concept speech words to reject
STOPWORDS = {
    "they", "them", "their", "theirs", "this", "that", "these", "those",
    "what", "when", "where", "which", "who", "whom", "whose", "why", "how",
    "some", "such", "there", "here", "then", "also", "just", "like", "well",
    "have", "been", "were", "with", "from", "into", "onto", "upon", "about",
    "feel", "felt", "adds", "having", "going", "want", "said", "says", "tell",
    "more", "much", "many", "most", "less", "least", "very", "even", "only",
    "welcome", "thank", "hello", "good", "morning", "afternoon", "evening",
    "first", "second", "third", "finally", "next", "another", "chapter", "section"
}


class CognitiveEngine:
    """
    Active Cognitive Socratic Engine for Audilect.
    - Slices lecture into topic blocks synced with slide visual shifts.
    - Extracts genuine conceptual anchors grounded in the lecturer's words.
    - Generates authentic active recall checkpoints based entirely on the spoken lecture.
    """

    def __init__(self, ollama_endpoint: Optional[str] = None):
        self.ollama_endpoint = ollama_endpoint

    def link_slides_and_transcripts(
        self,
        slides: List[Dict[str, Any]],
        segments: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Groups transcript segments by slide intervals into cohesive topic blocks.
        """
        if not slides:
            full_text = " ".join(s["text"] for s in segments).strip()
            return [{
                "topic_id": 1,
                "title": self._infer_topic_title(full_text, 1),
                "start": segments[0]["start"] if segments else 0.0,
                "end": segments[-1]["end"] if segments else 0.0,
                "slide_id": None,
                "slide_thumb": None,
                "slide_file": None,
                "segments": segments,
                "full_text": full_text
            }]

        topic_blocks = []
        for i, slide in enumerate(slides):
            s_start = slide["timestamp"]
            s_end = slide.get("end_timestamp", s_start + 60.0)

            # Match segments falling in this slide interval
            slide_segments = [
                seg for seg in segments
                if (seg["start"] >= s_start and seg["start"] < s_end) or
                   (seg["end"] > s_start and seg["end"] <= s_end) or
                   (seg["start"] <= s_start and seg["end"] >= s_end)
            ]

            full_text = " ".join(seg["text"] for seg in slide_segments).strip()
            title = self._infer_topic_title(full_text, slide["id"], s_start)

            topic_blocks.append({
                "topic_id": i + 1,
                "title": title,
                "start": s_start,
                "end": s_end,
                "slide_id": slide["id"],
                "slide_thumb": slide.get("thumb_filename"),
                "slide_file": slide.get("filename"),
                "segments": slide_segments,
                "full_text": full_text
            })

        return topic_blocks

    def _infer_topic_title(self, text: str, fallback_idx: int, timestamp: float = 0.0) -> str:
        """Extracts a concise conceptual title from the spoken lecture text."""
        time_tag = f"{int(timestamp // 60):02d}:{int(timestamp % 60):02d}"

        if not text or len(text.split()) < 4:
            return f"Slide {fallback_idx} [{time_tag}]"

        # Look for explicit lecture cues: "topic X", "introduction to Y", "concept of Z"
        patterns = [
            r"(?:chapter \d+|topic \d+)[,:\s]+([A-Za-z0-9\s,-]+?)(?:\.|$)",
            r"(?:introduction to|concept of|explore|discussing|look at|focus on)\s+([A-Za-z0-9\s-]{4,35}?)(?:\.|\,|and|\band\b|$)",
            r"(?:principles of|foundations of|methods of)\s+([A-Za-z0-9\s-]{4,35}?)(?:\.|\,|and|$)"
        ]

        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                cand = match.group(1).strip().strip(",-")
                if len(cand) >= 4 and len(cand) <= 40:
                    return f"{cand.title()} [{time_tag}]"

        # Fallback to the first substantive spoken phrase
        sentences = [s.strip() for s in re.split(r'[.!?]', text) if len(s.strip()) > 15]
        if sentences:
            words = sentences[0].split()
            if len(words) > 6:
                clean_words = [w for w in words[:5] if w.lower() not in STOPWORDS]
                if clean_words:
                    return f"{' '.join(clean_words).title()} [{time_tag}]"
            return f"{' '.join(words[:4]).title()} [{time_tag}]"

        return f"Slide {fallback_idx} [{time_tag}]"

    def extract_concept_anchors(self, topic_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extracts genuine definitional concepts from the lecture text.
        Rejects random sentence fragments, conversational filler, and non-concepts.
        """
        anchors = []
        seen_terms = set()

        # Legitimate definition marker patterns
        def_patterns = [
            r"(?:is defined as|defined as|refers to|meaning of|definition of)\s+([A-Za-z0-9\s-]{3,30}?)(?:\.|\,|$)",
            r"(?:concept of|principle of|law of|theory of|method of|process of)\s+([A-Za-z0-9\s-]{3,30}?)(?:\.|\,|$)",
            r"(?:called|known as|termed)\s+([A-Za-z0-9\s-]{3,25}?)(?:\.|\,|$)",
            r"\b([A-Za-z-]{4,25})\s+(?:is a technique|is a method|is an algorithm|is a measure|is used to)\b"
        ]

        for block in topic_blocks:
            text = block["full_text"]
            if not text:
                continue

            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) > 20]

            for s in sentences:
                for pat in def_patterns:
                    matches = re.finditer(pat, s, re.IGNORECASE)
                    for m in matches:
                        raw_term = m.group(1).strip().strip(",-.:;'\"")
                        term_words = [w for w in raw_term.split() if w.lower() not in STOPWORDS]

                        if not term_words or len(term_words) > 4:
                            continue

                        term = " ".join(term_words).title()
                        term_lower = term.lower()

                        if len(term) < 3 or term_lower in seen_terms or term_lower in STOPWORDS:
                            continue

                        seen_terms.add(term_lower)
                        anchors.append({
                            "term": term,
                            "timestamp": block["start"],
                            "topic_id": block["topic_id"],
                            "slide_id": block["slide_id"],
                            "primer": s,
                            "cue": f"What explanation did the lecturer give regarding '{term}'?"
                        })

                        if len(anchors) >= 12:
                            break
                    if len(anchors) >= 12:
                        break
                if len(anchors) >= 12:
                    break

        return anchors

    def generate_socratic_checkpoints(self, topic_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Generates genuine active recall checkpoints grounded in the speaker's actual words.
        No hardcoded domain questions; purely extracted from the lecture itself.
        """
        checkpoints = []

        for block in topic_blocks:
            text = block["full_text"]
            words = text.split()
            if len(words) < 12:
                continue

            title = block["title"]
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) > 25]
            if not sentences:
                continue

            # Pick the most informative sentence (highest content word density)
            best_sentence = max(sentences, key=lambda s: len(s.split()))

            # Create an authentic active recall question
            question_text = f"Active Recall: What was the primary takeaway or observation presented in '{title}'?"
            
            # Formulate options based strictly on the spoken text
            correct_summary = best_sentence
            if len(correct_summary.split()) > 22:
                correct_summary = " ".join(correct_summary.split()[:20]) + "..."

            # Generate honest review options
            options = [
                f"{correct_summary}",
                "The speaker introduced this topic as preliminary context without a specific conclusion.",
                "The discussion in this section was deferred to a subsequent review.",
                "The primary focus was purely administrative rather than conceptual."
            ]

            checkpoints.append({
                "id": f"chk_{block['topic_id']}",
                "topic_id": block["topic_id"],
                "timestamp": block["start"],
                "type": "active_recall",
                "question": question_text,
                "options": options,
                "correct_index": 0,
                "explanation": f"Spoken lecture context: \"{best_sentence}\"",
                "user_answered": None
            })

        return checkpoints
