# backend/main.py
from fastapi import FastAPI
from pydantic import BaseModel
from sudachipy import tokenizer, dictionary
from fastapi.middleware.cors import CORSMiddleware
import jaconv
import spacy
from jamdict import Jamdict
import re
import difflib

app = FastAPI(title="Subtitle Alignment Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize all our NLP and Dictionary tools globally so they stay in memory
tokenizer_obj = dictionary.Dictionary(dict="core").create()
mode = tokenizer.Tokenizer.SplitMode.C
nlp_en = spacy.load("en_core_web_sm")
jmd = Jamdict() 

class AlignmentPayload(BaseModel):
    ja_text: str
    en_text: str

# Distinct color palette for our matched pairs
PALETTE = ["#3B82F6", "#EF4444", "#10B981", "#F59E0B", "#8B5CF6", "#EC4899", "#06B6D4"]
DEFAULT_COLOR = "#9CA3AF"  # Muted gray for unmatched particles/grammar

@app.post("/api/v1/align")
async def align_subtitles(payload: AlignmentPayload):
    # --- 1. Parse the English Sentence ---
    doc_en = nlp_en(payload.en_text)
    en_tokens = []
    for token in doc_en:
        # Skip whitespaces AND punctuation
        if not token.is_space and not token.is_punct: 
            en_tokens.append({
                "word": token.text,
                "lemma": token.lemma_.lower(),
                "pair_id": None,
                "color": DEFAULT_COLOR
            })

    # --- 2. Parse the Japanese Sentence ---
    tokens_ja = tokenizer_obj.tokenize(payload.ja_text, mode)
    ja_tokens = []
    for t in tokens_ja:
        surface = t.surface()
        pos = t.part_of_speech()[0]
        lemma = t.dictionary_form()
        
        # Convert default Katakana reading to Hiragana
        reading = jaconv.kata2hira(t.reading_form())
        
        # Fix particle pronunciations
        if pos == "助詞":
            if surface == "は": reading = "わ"
            elif surface == "へ": reading = "え"
            elif surface == "を": reading = "お"
            
        # Prevent redundant furigana
        if surface == reading:
            reading = ""
            
        ja_tokens.append({
            "word": surface,
            "reading": reading,
            "lemma": lemma,
            "pos": pos,
            "pair_id": None,
            "color": DEFAULT_COLOR
        })
        # --- 3. The Bipartite Alignment Algorithm ---
    pair_counter = 1
    
    for ja_idx, ja_t in enumerate(ja_tokens):
        if ja_t["pos"] in ["助詞", "助動詞", "記号"]:
            continue 
            
        result = jmd.lookup(ja_t["lemma"])
        
        gloss_words = set()
        for entry in result.entries:
            for sense in entry.senses:
                # CORRECTED: iterate through the gloss objects properly
                for gloss in sense.gloss: 
                    clean_gloss = re.sub(r'[^a-zA-Z\s]', '', gloss.text)
                    gloss_words.update(clean_gloss.lower().split())
                    
        # Let's print to the terminal so we can see what the dictionary found!
        print(f"Checking Japanese: {ja_t['word']} (Lemma: {ja_t['lemma']})")
        print(f"-> JMDict English Meanings: {gloss_words}")
                    
        for en_idx, en_t in enumerate(en_tokens):
            if en_t["pair_id"] is not None:
                continue 
                
            en_lemma = en_t["lemma"]
            is_match = en_lemma in gloss_words
            
            if not is_match:
                matches = difflib.get_close_matches(en_lemma, gloss_words, n=1, cutoff=0.85)
                if matches:
                    is_match = True
                    
            if is_match:
                print(f"   [SUCCESS] Matched with English: {en_t['word']}!\n")
                color = PALETTE[pair_counter % len(PALETTE)]
                
                ja_tokens[ja_idx]["pair_id"] = pair_counter
                ja_tokens[ja_idx]["color"] = color
                
                en_tokens[en_idx]["pair_id"] = pair_counter
                en_tokens[en_idx]["color"] = color
                
                pair_counter += 1
                break
        
    # Clean up the payload slightly by removing backend-only fields like 'lemma' and 'pos'
    for t in ja_tokens:
        t.pop("lemma", None)
        t.pop("pos", None)
    for t in en_tokens:
        t.pop("lemma", None)

    return {
        "japanese": ja_tokens,
        "english": en_tokens
    }
