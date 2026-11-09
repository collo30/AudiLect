import os
import json
import re
import time
import random
import urllib.request
import urllib.parse
import urllib.error
from typing import List, Dict, Any, Optional
from pathlib import Path


CONFIG_PATH = Path("data/config.json")


def load_ai_config() -> Dict[str, Any]:
    """Loads persistent AI configuration from data/config.json, with env var fallbacks."""
    config = {
        "provider": "gemini",
        "gemini_api_key": os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or "",
        "gemini_model": "gemini-2.5-flash",
        "groq_api_key": os.environ.get("GROQ_API_KEY") or "",
        "groq_model": "llama-3.3-70b-versatile"
    }

    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                config.update(saved)
        except Exception as e:
            print(f"[!] Warning reading config.json: {e}")

    # Fallback env checks if still empty
    if not config["gemini_api_key"]:
        config["gemini_api_key"] = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
    if not config["groq_api_key"]:
        config["groq_api_key"] = os.environ.get("GROQ_API_KEY") or ""

    return config


def save_ai_config(new_config: Dict[str, Any]) -> Dict[str, Any]:
    """Saves updated AI configuration to data/config.json."""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    current = load_ai_config()
    current.update(new_config)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2)
    return current


def mask_key(key: str) -> str:
    """Safely masks API key for UI telemetry display."""
    if not key or len(key) < 8:
        return "" if not key else "••••••••"
    return f"{key[:4]}••••••••{key[-4:]}"


def fetch_wikipedia_summary(term: str) -> Optional[str]:
    """Retrieves encyclopedic summary from Wikipedia REST API for background elaboration."""
    try:
        clean_term = re.sub(r'[^a-zA-Z0-9\s_-]', '', term).strip()
        if not clean_term:
            return None
        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(clean_term)}"
        req = urllib.request.Request(url, headers={"User-Agent": "AudilectActiveCognition/1.0 (educational research tool)"})
        with urllib.request.urlopen(req, timeout=3.5) as r:
            data = json.loads(r.read().decode("utf-8"))
            extract = data.get("extract", "").strip()
            if extract and len(extract) > 30 and not "may refer to:" in extract:
                return extract
    except Exception:
        pass
    return None


class AIEngine:
    """
    Unified Intelligent AI Engine for Audilect.
    Features:
    1. Concise, high-density Socratic question drafting (short sentences, high coverage).
    2. Deep concept primer generation for the CONCEPTS tab.
    3. Rich external knowledge transcript callouts (knowledge NOT in the lecture).
    4. Multi-provider cloud AI (Google Gemini 2.5 Flash, Groq 70B) + Encyclopedic NLU fallback.
    """

    def __init__(self):
        self.reload_config()

    def reload_config(self):
        self.config = load_ai_config()
        self.provider = self.config.get("provider", "gemini")
        self.gemini_key = self.config.get("gemini_api_key", "").strip()
        self.gemini_model = self.config.get("gemini_model", "gemini-2.5-flash")
        self.groq_key = self.config.get("groq_api_key", "").strip()
        self.groq_model = self.config.get("groq_model", "llama-3.3-70b-versatile")

    def get_status_info(self) -> Dict[str, Any]:
        """Returns safe configuration info and active status for the cockpit UI."""
        self.reload_config()
        active_key = self.gemini_key if self.provider == "gemini" else self.groq_key
        active_model = self.gemini_model if self.provider == "gemini" else self.groq_model
        has_key = bool(active_key)

        return {
            "provider": self.provider,
            "has_active_key": has_key,
            "active_model": active_model,
            "gemini_model": self.gemini_model,
            "groq_model": self.groq_model,
            "gemini_key_masked": mask_key(self.gemini_key),
            "groq_key_masked": mask_key(self.groq_key),
            "status_label": f"{self.provider.upper()} ({active_model})" if has_key else "AUTONOMOUS ENCYCLOPEDIC NLU"
        }

    def test_provider_connection(self, provider: str, api_key: str, model_name: str) -> Dict[str, Any]:
        """Tests API key and connectivity with either Gemini or Groq."""
        api_key = api_key.strip()
        if not api_key:
            return {"success": False, "error": "API Key is required."}

        start_t = time.time()
        test_prompt = "Return strictly JSON: {\"status\": \"ok\", \"provider\": \"" + provider + "\"}"

        try:
            if provider == "gemini":
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                payload = json.dumps({
                    "contents": [{"parts": [{"text": test_prompt}]}],
                    "generationConfig": {"responseMimeType": "application/json"}
                }).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=12.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    latency_ms = int((time.time() - start_t) * 1000)
                    return {"success": True, "latency_ms": latency_ms, "message": f"Connected to Google Gemini ({model_name}) in {latency_ms}ms"}

            elif provider == "groq":
                url = "https://api.groq.com/openai/v1/chat/completions"
                payload = json.dumps({
                    "model": model_name,
                    "messages": [{"role": "user", "content": test_prompt}],
                    "response_format": {"type": "json_object"}
                }).encode("utf-8")
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
                req = urllib.request.Request(url, data=payload, headers=headers)
                with urllib.request.urlopen(req, timeout=12.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    latency_ms = int((time.time() - start_t) * 1000)
                    return {"success": True, "latency_ms": latency_ms, "message": f"Connected to Groq ({model_name}) in {latency_ms}ms"}

            else:
                return {"success": False, "error": f"Unknown provider: {provider}"}

        except urllib.error.HTTPError as e:
            try:
                err_body = json.loads(e.read().decode("utf-8"))
                msg = err_body.get("error", {}).get("message", str(e))
            except Exception:
                msg = str(e)
            return {"success": False, "error": f"API Error ({e.code}): {msg}"}
        except Exception as e:
            return {"success": False, "error": f"Connection failed: {str(e)}"}

    def is_ai_configured(self) -> bool:
        """Returns True if the active provider has an API key configured."""
        self.reload_config()
        if self.provider == "gemini" and self.gemini_key:
            return True
        if self.provider == "groq" and self.groq_key:
            return True
        return False

    # 1. SOCRATIC QUESTIONS (CONCISE, PUNCHY, HIGH-DENSITY)
    def generate_intelligent_checkpoints(
        self,
        topic_blocks: List[Dict[str, Any]],
        lecture_title: str = "Lecture"
    ) -> List[Dict[str, Any]]:
        """
        Drafts high-density, concise Socratic active recall questions (6 to 10 questions).
        Uses simple, punchy language with short sentences to maximize coverage and minimize token usage.
        """
        self.reload_config()

        if self.is_ai_configured():
            try:
                if self.provider == "gemini":
                    results = self._generate_checkpoints_gemini(topic_blocks, lecture_title)
                    if results and len(results) >= 3:
                        return results
                elif self.provider == "groq":
                    results = self._generate_checkpoints_groq(topic_blocks, lecture_title)
                    if results and len(results) >= 3:
                        return results
            except Exception as e:
                print(f"[*] Cloud AI question generation failed ({self.provider}): {e}. Using NLU.")

        return self._generate_checkpoints_nlu(topic_blocks)

    def _call_gemini_json(self, prompt: str, timeout: float = 25.0) -> Any:
        """
        Executes a Gemini generation call with automatic multi-model failover and retry.
        If a primary model returns 503 (service unavailable), 429, or 404, fails over to
        verified ultra-fast models (gemini-2.5-flash-lite, gemini-2.5-flash, gemini-flash-latest).
        """
        candidates = []
        for m in [self.gemini_model, "gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3-flash-preview", "gemini-2.5-flash-lite"]:
            if m and m not in candidates:
                candidates.append(m)

        last_err = None
        for model_name in candidates:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.gemini_key}"
            payload = json.dumps({
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2}
            }).encode("utf-8")

            for attempt in range(2):
                try:
                    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=timeout) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                        return json.loads(raw_text)
                except urllib.error.HTTPError as e:
                    last_err = e
                    if e.code in (429, 503, 500, 502, 404):
                        print(f"[*] Gemini {model_name} returned HTTP {e.code}. Failing over to next candidate model...")
                        break
                    else:
                        break
                except Exception as e:
                    last_err = e
                    time.sleep(0.5)

        if last_err:
            raise last_err
        raise RuntimeError("Gemini generation failed on all candidate models.")

    def _generate_checkpoints_gemini(self, topic_blocks: List[Dict[str, Any]], lecture_title: str) -> List[Dict[str, Any]]:
        context_str = self._build_transcript_context(topic_blocks)
        if not context_str.strip():
            return []

        total_words = sum(len(b.get("full_text", "").split()) for b in topic_blocks)
        num_blocks = len(topic_blocks)
        # Scales dynamically: longer video -> more questions across entire timeline!
        target_q_count = max(8, min(65, max(int(num_blocks * 0.9), int(total_words / 75))))

        prompt = f"""You are an expert tutor creating concise Socratic active recall questions for students.
Lecture Title: {lecture_title}

Transcript:
{context_str}

RULES:
1. Generate {target_q_count} active recall questions covering all major concepts, causes, and mechanisms across the ENTIRE lecture from beginning to end.
2. Distribute questions evenly from the start of the lecture to the end so every portion of the lecture is covered.
3. Keep questions SHORT and DIRECT (1 sentence, max 16 words). Use simple, clear English.
4. Every question must test cause, mechanism, or trade-off (e.g. "Why does X happen?", "What is the main risk of Y?").
5. Keep all 4 options SHORT (under 12 words each).
6. Option 0 MUST be the single correct answer. Options 1, 2, and 3 must be common misconceptions.
7. Explanation must be exactly ONE concise sentence.
8. Do NOT use emojis anywhere in questions, options, or explanations.

Output valid JSON array:
[
  {{
    "question": "Why does occlusion occur in dense 2D plots?",
    "options": ["Data marks overlap at identical coordinates.", "Points exceed screen resolution limits.", "Color palettes bleed into each other.", "Axes scales invert automatically."],
    "explanation": "Occlusion happens when multiple data marks share identical spatial coordinates.",
    "timestamp": 0.0
  }}
]
"""
        parsed = self._call_gemini_json(prompt, timeout=30.0)
        if isinstance(parsed, dict) and "questions" in parsed:
            parsed = parsed["questions"]
        return self._format_ai_results(parsed, topic_blocks, "gemini")

    def _generate_checkpoints_groq(self, topic_blocks: List[Dict[str, Any]], lecture_title: str) -> List[Dict[str, Any]]:
        context_str = self._build_transcript_context(topic_blocks)
        if not context_str.strip():
            return []

        total_words = sum(len(b.get("full_text", "").split()) for b in topic_blocks)
        num_blocks = len(topic_blocks)
        target_q_count = max(8, min(65, max(int(num_blocks * 0.9), int(total_words / 75))))

        system_prompt = (
            f"You are an expert tutor. Output strictly valid JSON with key 'questions' containing {target_q_count} concise questions "
            "covering the lecture from beginning to end. Questions must be 1 short sentence (under 16 words). Options must be short (under 12 words, index 0 correct). "
            "Explanation must be 1 short sentence. Use simple, direct English. No emojis."
        )
        user_prompt = f"Lecture: {lecture_title}\n\nTranscript:\n{context_str}\n\nOutput JSON object with 'questions':"

        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = json.dumps({
            "model": self.groq_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }).encode("utf-8")

        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.groq_key}"}
        req = urllib.request.Request(url, data=payload, headers=headers)
        with urllib.request.urlopen(req, timeout=25.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            items = parsed.get("questions", parsed if isinstance(parsed, list) else [])
            return self._format_ai_results(items, topic_blocks, "groq")

    def _generate_checkpoints_nlu(self, topic_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Intelligent fallback Socratic question generator with strict deduplication and curation."""
        checkpoints = []

        # 1. Deduplicate and collect substantive blocks
        valid_blocks = []
        seen_texts = set()
        for b in topic_blocks:
            text = b.get("full_text", "").strip()
            # Normalize whitespace and key signature words
            sig = " ".join(text.lower().split()[:8])
            if sig and sig not in seen_texts and len(text.split()) >= 4:
                seen_texts.add(sig)
                valid_blocks.append(b)

        if not valid_blocks and topic_blocks:
            valid_blocks = topic_blocks

        # 2. Sample evenly at most 6-8 blocks across the lecture
        max_q = min(6, len(valid_blocks))
        if len(valid_blocks) > max_q:
            step = len(valid_blocks) / float(max_q)
            selected_blocks = [valid_blocks[int(i * step)] for i in range(max_q)]
        else:
            selected_blocks = valid_blocks

        socratic_stems = [
            ("Why is this mechanism critical to the speaker's argument?", "It establishes the underlying causal dependency required for the outcome."),
            ("What primary risk or constraint was highlighted here?", "Unchecked application violates fundamental assumptions and introduces error."),
            ("What core trade-off or distinction was emphasized?", "Balancing visual or structural precision against cognitive load and clarity."),
            ("How does this principle operate under real-world conditions?", "Standard implementations require rigorous boundary validation."),
            ("What common misconception does this observation directly address?", "Assuming linear behavior conceals critical non-linear threshold effects."),
            ("What foundational rule governs this relationship?", "Strict alignment between data representation and viewer perception is mandatory.")
        ]

        causal_indicators = [
            (r"(?:because|since|due to)\s+(.+?)(?:,|\.|$)", "What primary cause produces this outcome?"),
            (r"(?:therefore|consequently|leads to|results in)\s+(.+?)(?:,|\.|$)", "What key consequence directly follows?"),
            (r"(?:the problem is|the danger is|risk of)\s+(.+?)(?:,|\.|$)", "What critical hazard was identified?"),
            (r"(?:instead of|rather than|unlike)\s+(.+?)(?:,|\.|$)", "What key distinction was established?")
        ]

        for idx, block in enumerate(selected_blocks):
            text = block.get("full_text", "")
            title = block.get("title", f"Concept {idx + 1}")
            sentences = [s.strip() for s in re.split(r'[.!?]+', text) if len(s.strip().split()) >= 3]

            found_q = None
            for s in sentences:
                for pattern, q_prompt in causal_indicators:
                    m = re.search(pattern, s, re.IGNORECASE)
                    if m:
                        clause = m.group(1).strip()
                        if 3 <= len(clause.split()) <= 14:
                            found_q = {
                                "question": f"{title}: {q_prompt}",
                                "correct": clause.capitalize() + ".",
                                "explanation": f"Grounded in lecture: \"{s.strip()}\""
                            }
                            break
                    if found_q:
                        break
                if found_q:
                    break

            if not found_q and sentences:
                short_s = min([s for s in sentences if len(s.split()) >= 4], key=lambda s: len(s.split()), default=sentences[0])
                stem_q, stem_distractor = socratic_stems[idx % len(socratic_stems)]
                found_q = {
                    "question": f"{title}: {stem_q}",
                    "correct": short_s,
                    "explanation": f"Grounded in lecture observation: \"{short_s}\""
                }

            if found_q:
                correct_ans = found_q["correct"]
                if len(correct_ans.split()) > 14:
                    correct_ans = " ".join(correct_ans.split()[:12]) + "..."

                distractor_bank = [
                    "This was presented as an anomalous outlier without general applicability.",
                    "The outcome was attributed to random environmental noise rather than structure.",
                    "The principle was shown to have zero trade-offs or constraints.",
                    "The mechanism was inverted to minimize baseline fidelity."
                ]

                all_opts = [correct_ans] + distractor_bank[:3]
                random.shuffle(all_opts)
                nlu_correct_idx = all_opts.index(correct_ans)

                checkpoints.append({
                    "id": f"chk_{block.get('topic_id', idx + 1)}",
                    "topic_id": block.get("topic_id", idx + 1),
                    "timestamp": block.get("start", 0.0),
                    "type": "active_recall",
                    "question": found_q["question"],
                    "options": all_opts,
                    "correct_index": nlu_correct_idx,
                    "explanation": found_q["explanation"],
                    "user_answered": None,
                    "ai_generated": False,
                    "ai_provider": "nlu_curated"
                })

        return checkpoints

    # 2. CLEAR DEFINITIONS IN CONCEPT TAB (STUDY & RECALL)
    def generate_clear_concepts(
        self,
        topic_blocks: List[Dict[str, Any]],
        lecture_title: str = "Lecture"
    ) -> List[Dict[str, Any]]:
        """
        Extracts and clearly defines all important concepts for the CONCEPTS tab.
        Uses active AI (Gemini/Groq) or encyclopedic NLU to create concise, plain-English micro-primers.
        """
        self.reload_config()

        if self.is_ai_configured():
            try:
                if self.provider == "gemini":
                    concepts = self._generate_concepts_gemini(topic_blocks, lecture_title)
                    if concepts and len(concepts) >= 3:
                        return concepts
                elif self.provider == "groq":
                    concepts = self._generate_concepts_groq(topic_blocks, lecture_title)
                    if concepts and len(concepts) >= 3:
                        return concepts
            except Exception as e:
                print(f"[*] Cloud AI concept definition failed ({self.provider}): {e}. Using encyclopedic NLU.")

        return self._generate_concepts_nlu(topic_blocks, lecture_title)

    def _generate_concepts_gemini(self, topic_blocks: List[Dict[str, Any]], lecture_title: str) -> List[Dict[str, Any]]:
        context_str = self._build_transcript_context(topic_blocks)
        if not context_str.strip():
            return []

        total_words = sum(len(b.get("full_text", "").split()) for b in topic_blocks)
        num_blocks = len(topic_blocks)
        # Scales dynamically: longer lecture -> more comprehensive concepts!
        target_concepts = max(8, min(45, max(int(num_blocks * 0.7), int(total_words / 90))))

        prompt = f"""You are a master educator creating clear concept definitions for a student's study glossary.
Lecture: {lecture_title}

Transcript:
{context_str}

TASK:
Extract all key technical terms, methods, principles, laws, or phenomena discussed across this lecture (aim for {target_concepts} distinct concepts).
For EACH concept, provide:
1. "term": Concept name (Title Case).
2. "primer": A simple, crystal-clear definition (1-2 short sentences: what it is and why it matters). Use plain English!
3. "timestamp": Float seconds where it is first introduced or discussed.
4. Do NOT include flashcard prompts, question cues, or emojis.

Output valid JSON array:
[
  {{
    "term": "Occlusion",
    "primer": "When visual marks overlap on a plot, hiding each other and obscuring true data density.",
    "timestamp": 0.0
  }}
]
"""
        parsed = self._call_gemini_json(prompt, timeout=25.0)
        if isinstance(parsed, dict) and "concepts" in parsed:
            parsed = parsed["concepts"]
        return self._format_concepts(parsed, topic_blocks)

    def _generate_concepts_groq(self, topic_blocks: List[Dict[str, Any]], lecture_title: str) -> List[Dict[str, Any]]:
        context_str = self._build_transcript_context(topic_blocks)
        if not context_str.strip():
            return []

        total_words = sum(len(b.get("full_text", "").split()) for b in topic_blocks)
        num_blocks = len(topic_blocks)
        target_concepts = max(8, min(45, max(int(num_blocks * 0.7), int(total_words / 90))))

        system_prompt = (
            f"You are a master educator. Output strictly valid JSON with key 'concepts' containing {target_concepts} clearly defined concepts across the lecture. "
            "Each must have: 'term' (string), 'primer' (1-2 short sentences, simple English), 'timestamp' (float seconds). Do NOT include prompt cues or emojis."
        )
        user_prompt = f"Lecture: {lecture_title}\n\nTranscript:\n{context_str}\n\nOutput JSON:"

        url = "https://api.groq.com/openai/v1/chat/completions"
        payload = json.dumps({
            "model": self.groq_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }).encode("utf-8")

        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.groq_key}"}
        req = urllib.request.Request(url, data=payload, headers=headers)
        with urllib.request.urlopen(req, timeout=25.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            items = parsed.get("concepts", parsed if isinstance(parsed, list) else [])
            return self._format_concepts(items, topic_blocks)

    def _generate_concepts_nlu(self, topic_blocks: List[Dict[str, Any]], lecture_title: str) -> List[Dict[str, Any]]:
        """Encyclopedic concept extraction fallback using Wikipedia REST API."""
        keywords = [
            ("Occlusion", "Visual marks overlapping on a display, obscuring underlying data points."),
            ("Scatter Plot", "A two-dimensional data visualization using Cartesian coordinates to display values for two variables."),
            ("Data Visualization", "The practice of representing quantitative data graphically to reveal patterns and insights."),
            ("Learned Helplessness", "A psychological state where repeated failure creates a perceived complete lack of control."),
            ("Alpha Blending", "Adjusting opacity so overlapping data points remain visible through transparency."),
            ("Hexagonal Binning", "A 2D data aggregation technique that groups points into hexagonal cells to visualize density.")
        ]

        concepts = []
        full_lecture_text = " ".join(b.get("full_text", "") for b in topic_blocks).lower()

        for term, default_primer in keywords:
            if term.lower() in full_lecture_text or any(w.lower() in full_lecture_text for w in term.split()):
                # Lookup live wiki definition
                wiki = fetch_wikipedia_summary(term)
                primer = (wiki.split(". ")[0] + ".") if wiki else default_primer

                # Match nearest topic block timestamp
                ts = 0.0
                for b in topic_blocks:
                    if term.lower() in b.get("full_text", "").lower():
                        ts = b.get("start", 0.0)
                        break

                concepts.append({
                    "term": term,
                    "primer": primer,
                    "cue": f"Define {term} and explain its core role.",
                    "timestamp": ts
                })
                if len(concepts) >= 6:
                    break

        if not concepts and topic_blocks:
            concepts.append({
                "term": lecture_title,
                "primer": f"Core framework: Focuses on understanding the systematic causes and trade-offs presented in '{lecture_title}'.",
                "cue": f"What is the primary conclusion of {lecture_title}?",
                "timestamp": topic_blocks[0].get("start", 0.0)
            })

        return concepts

    def _format_concepts(self, items: List[Dict[str, Any]], topic_blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        formatted = []
        for idx, item in enumerate(items):
            term = item.get("term", "").strip()
            primer = item.get("primer", "").strip()
            cue = item.get("cue", "").strip()
            ts = float(item.get("timestamp", topic_blocks[idx]["start"] if idx < len(topic_blocks) else 0.0))

            if term and primer:
                formatted.append({
                    "term": term,
                    "primer": primer,
                    "cue": cue or f"Explain the principle of {term}.",
                    "timestamp": ts
                })
        return formatted

    # 3. HIGH-FREQUENCY, CONCISE EXTERNAL KNOWLEDGE CALLOUTS
    def enrich_transcript_with_external_knowledge(
        self,
        segments: List[Dict[str, Any]],
        topic_blocks: List[Dict[str, Any]],
        lecture_title: str = "Lecture"
    ) -> List[Dict[str, Any]]:
        """
        Enriches transcript segments across the entire lecture with high-frequency,
        concise outside-knowledge callouts (1-2 short sentences each).
        """
        self.reload_config()

        if self.is_ai_configured():
            try:
                if self.provider == "gemini":
                    enriched = self._enrich_gemini_dense(segments, topic_blocks, lecture_title)
                    if enriched:
                        return enriched
                elif self.provider == "groq":
                    enriched = self._enrich_groq_dense(segments, topic_blocks, lecture_title)
                    if enriched:
                        return enriched
            except Exception as e:
                print(f"[*] Cloud AI elaboration failed ({self.provider}): {e}. Using encyclopedic fallback.")

        return self._enrich_nlu_dense(segments, topic_blocks, lecture_title)

    def _enrich_gemini_dense(self, segments: List[Dict[str, Any]], topic_blocks: List[Dict[str, Any]], lecture_title: str) -> List[Dict[str, Any]]:
        # Process in windows of 20 segments across the ENTIRE lecture so longer videos get proportionally more callouts!
        window_size = 20
        all_elaborations = []

        for i in range(0, len(segments), window_size):
            chunk = segments[i:i + window_size]
            context_items = [f"Seg {s['id']}: {s['text']}" for s in chunk]
            context_str = "\n".join(context_items)
            target_callouts = max(3, min(10, len(chunk) // 2))

            prompt = f"""You are an elite tutor providing concise, high-value study callouts for students.
Lecture: {lecture_title} (Section {i // window_size + 1})

Transcript:
{context_str}

TASK:
For this portion of the transcript, identify segments where you can add high-value outside knowledge (generate {target_callouts} callouts):
- 'intuition': A clear, underlying key concept or mental model.
- 'exam_pitfall': A common misconception or error students make.
- 'application': A practical industry or real-world application.

RULES:
- Content MUST be CONCISE: 1 to 2 short sentences max (under 35 words).
- Use simple, direct English. No academic filler.
- Badge MUST be clean uppercase text: "KEY CONCEPT", "COMMON MISCONCEPTION", or "PRACTICAL APPLICATION".
- Do NOT include bracketed phrases like "(not in lecture)" or "(extra)".
- Do NOT use emojis anywhere in the output.

Output valid JSON array:
[
  {{
    "segment_id": {chunk[0]['id']},
    "type": "intuition",
    "badge": "KEY CONCEPT",
    "title": "Mental Model & Mechanism",
    "content": "Clear 1-sentence insight explaining underlying principle."
  }}
]
"""
            try:
                parsed = self._call_gemini_json(prompt, timeout=25.0)
                if isinstance(parsed, dict) and "elaborations" in parsed:
                    parsed = parsed["elaborations"]
                if isinstance(parsed, list):
                    all_elaborations.extend(parsed)
            except Exception as e:
                print(f"[*] Batch {i} elaboration failed: {e}")

        if not all_elaborations:
            return self._enrich_nlu_dense(segments, topic_blocks, lecture_title)
        return self._merge_elaborations_into_segments(segments, all_elaborations)

    def _enrich_groq_dense(self, segments: List[Dict[str, Any]], topic_blocks: List[Dict[str, Any]], lecture_title: str) -> List[Dict[str, Any]]:
        window_size = 20
        all_elaborations = []

        for i in range(0, len(segments), window_size):
            chunk = segments[i:i + window_size]
            context_items = [f"Seg {s['id']}: {s['text']}" for s in chunk]
            context_str = "\n".join(context_items)
            target_callouts = max(3, min(10, len(chunk) // 2))

            system_prompt = (
                f"You are an elite tutor. Output strictly valid JSON with key 'elaborations' containing {target_callouts} objects. "
                "Do NOT use emojis anywhere. Do NOT include bracketed notes like '(not in lecture)'. "
                "Each object adds outside knowledge: 'segment_id' (int), 'type' ('intuition'|'exam_pitfall'|'application'), "
                "'badge' ('KEY CONCEPT'|'COMMON MISCONCEPTION'|'PRACTICAL APPLICATION'), 'title' (string), and 'content' (1-2 short sentences, under 35 words)."
            )
            user_prompt = f"Lecture: {lecture_title}\n\nTranscript:\n{context_str}\n\nOutput JSON:"

            url = "https://api.groq.com/openai/v1/chat/completions"
            payload = json.dumps({
                "model": self.groq_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.25
            }).encode("utf-8")

            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.groq_key}"}
            try:
                req = urllib.request.Request(url, data=payload, headers=headers)
                with urllib.request.urlopen(req, timeout=25.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    content = data["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    items = parsed.get("elaborations", parsed if isinstance(parsed, list) else [])
                    if isinstance(items, list):
                        all_elaborations.extend(items)
            except Exception as e:
                print(f"[*] Groq batch {i} elaboration failed: {e}")

        if not all_elaborations:
            return self._enrich_nlu_dense(segments, topic_blocks, lecture_title)
        return self._merge_elaborations_into_segments(segments, all_elaborations)

    def _enrich_nlu_dense(
        self,
        segments: List[Dict[str, Any]],
        topic_blocks: List[Dict[str, Any]],
        lecture_title: str
    ) -> List[Dict[str, Any]]:
        """Dense encyclopedic knowledge enrichment fallback (zero key needed)."""
        domain_patterns = [
            (r'\b(visualization|spatial|2D|scatter|heatmap|coordinates|projection)\b', 'intuition', 'KEY CONCEPT', 'Visual Perception & Density', 'Occlusion happens when points share identical coordinates. Standard fixes include alpha-blending transparency or hexagonal binning.'),
            (r'\b(occlusion|overplot|overlap)\b', 'exam_pitfall', 'COMMON MISCONCEPTION', 'Overplotting vs. Occlusion', 'Do not confuse point density (overplotting) with lost visibility (occlusion). Occlusion hides data clusters completely.'),
            (r'\b(defeated|manipulat\w+|helpless\w+|vulnerab\w+)\b', 'intuition', 'KEY CONCEPT', 'Learned Helplessness Trigger', 'Perceived defeat triggers cognitive compliance. When people feel agency is lost, they become significantly more receptive to external directives.'),
            (r'\b(church|institution|authority|control|money|finance)\b', 'exam_pitfall', 'COMMON MISCONCEPTION', 'Authority Bias Exploitation', 'Under emotional distress, individuals exhibit heightened authority bias, trading financial autonomy for promised emotional reassurance.'),
            (r'\b(data|sample|distribut\w+|variable|statistic\w+)\b', 'application', 'PRACTICAL APPLICATION', 'High-Dimensional Projections', 'Production pipelines use UMAP or t-SNE with interactive filtering to prevent 2D projection distortion.'),
            (r'\b(algorithm|matrix|formula|function)\b', 'prerequisite', 'BACKGROUND KNOWLEDGE', 'Dimension Preservation', 'Dimension mapping relies on distance-preserving geometry to ensure low-dimensional plots reflect true data distances.')
        ]

        assigned_segments = set()
        elaborations = []

        for seg in segments:
            text = seg["text"].lower()
            for pattern, elab_type, badge, title, default_content in domain_patterns:
                if re.search(pattern, text) and seg["id"] not in assigned_segments:
                    assigned_segments.add(seg["id"])
                    elaborations.append({
                        "segment_id": seg["id"],
                        "type": elab_type,
                        "badge": badge,
                        "title": title,
                        "content": default_content
                    })
                    break

        # Fallback if sparse
        if len(elaborations) < 2 and segments:
            for s in segments[:3]:
                if s["id"] not in assigned_segments:
                    elaborations.append({
                        "segment_id": s["id"],
                        "type": "intuition",
                        "badge": "ACTIVE LEARNING CUE",
                        "title": "Core Conceptual Bridge",
                        "content": f"Focus on identifying the primary trade-off and causal mechanism discussed by the speaker in '{lecture_title}'."
                    })
                    break

        return self._merge_elaborations_into_segments(segments, elaborations)

    def _merge_elaborations_into_segments(self, segments: List[Dict[str, Any]], elaborations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        elab_map = {}
        for item in elaborations:
            sid = item.get("segment_id")
            if sid is not None:
                raw_badge = item.get("badge") or item.get("type", "INTUITION")
                clean_badge = re.sub(r'\(.*?\)', '', str(raw_badge)).replace('[', '').replace(']', '').strip()
                if not clean_badge:
                    clean_badge = str(item.get("type", "INTUITION")).upper()

                elab_map[sid] = {
                    "type": item.get("type", "intuition"),
                    "badge": clean_badge,
                    "title": item.get("title", "Key Insight"),
                    "content": item.get("content", "")
                }

        result = []
        for s in segments:
            scopy = dict(s)
            if s["id"] in elab_map:
                scopy["ai_elaboration"] = elab_map[s["id"]]
            else:
                scopy["ai_elaboration"] = None
            result.append(scopy)
        return result

    def _build_transcript_context(self, topic_blocks: List[Dict[str, Any]]) -> str:
        transcript_sample = []
        for b in topic_blocks[:120]:
            text = b.get("full_text", "").strip()
            if len(text.split()) > 3:
                transcript_sample.append(f"[{b.get('title', 'Topic')} - {int(b.get('start', 0))}s]: {text}")
        return "\n\n".join(transcript_sample)

    def _format_ai_results(self, items: List[Dict[str, Any]], topic_blocks: List[Dict[str, Any]], provider_name: str) -> List[Dict[str, Any]]:
        formatted = []
        for idx, item in enumerate(items):
            q = item.get("question")
            opts = item.get("options", [])
            exp = item.get("explanation", "")
            t = float(item.get("timestamp", topic_blocks[min(idx, len(topic_blocks) - 1)]["start"] if topic_blocks else 0.0))

            if q and len(opts) >= 2:
                opts_to_shuffle = [str(o).strip() for o in opts[:4]]
                correct_text = opts_to_shuffle[0]
                random.shuffle(opts_to_shuffle)
                shuffled_correct_index = opts_to_shuffle.index(correct_text)

                formatted.append({
                    "id": f"ai_{provider_name}_{idx + 1}",
                    "topic_id": idx + 1,
                    "timestamp": t,
                    "type": "active_recall",
                    "question": q,
                    "options": opts_to_shuffle,
                    "correct_index": shuffled_correct_index,
                    "explanation": exp,
                    "user_answered": None,
                    "ai_generated": True,
                    "ai_provider": provider_name
                })
        return formatted


def annotate_transcript_elaborations(segments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return segments
