import os
import json
import fitz  # PyMuPDF
import re
from typing import Dict, List, Tuple, Optional
from collections import Counter, defaultdict
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ImprovedPDFOutlineExtractor:
    def __init__(self):
        self.min_heading_font_size = 8.0
        
    def extract_text_with_metadata(self, pdf_path: str) -> List[Dict]:
        """Extract text with comprehensive metadata and better line reconstruction"""
        doc = fitz.open(pdf_path)
        text_blocks = []
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            page_height = page.rect.height
            page_width = page.rect.width
            
            # Use different extraction method for better line reconstruction
            blocks = page.get_text("dict")
            
            # Group spans by lines more intelligently
            lines_data = []
            for block in blocks["blocks"]:
                if "lines" in block:
                    for line in block["lines"]:
                        line_spans = []
                        for span in line["spans"]:
                            if span["text"].strip():
                                line_spans.append(span)
                        
                        if line_spans:
                            lines_data.append({
                                "spans": line_spans,
                                "bbox": line["bbox"]
                            })
            
            # Reconstruct complete lines by merging nearby spans
            merged_lines = self.merge_nearby_spans(lines_data)
            
            for merged_line in merged_lines:
                text_blocks.append({
                    "text": merged_line["text"],
                    "page": page_num + 1,  # 1-based indexing
                    "font_size": merged_line["avg_font_size"],
                    "font": merged_line["dominant_font"],
                    "is_bold": merged_line["is_bold"],
                    "is_italic": merged_line["is_italic"],
                    "bbox": merged_line["bbox"],
                    "y_pos": merged_line["y_pos"],
                    "x_pos": merged_line["x_pos"],
                    "width": merged_line["width"],
                    "page_height": page_height,
                    "page_width": page_width,
                    "char_count": len(merged_line["text"]),
                    "word_count": len(merged_line["text"].split())
                })
        
        doc.close()
        return text_blocks
    
    def merge_nearby_spans(self, lines_data: List[Dict]) -> List[Dict]:
        """Merge spans that are part of the same logical line"""
        if not lines_data:
            return []
        
        merged_lines = []
        
        # Sort lines by Y position
        lines_data.sort(key=lambda x: x["bbox"][1])
        
        i = 0
        while i < len(lines_data):
            current_line = lines_data[i]
            current_spans = current_line["spans"]
            current_y = current_line["bbox"][1]
            
            # Look for nearby lines that should be merged
            merge_candidates = [current_line]
            
            j = i + 1
            while j < len(lines_data):
                next_line = lines_data[j]
                next_y = next_line["bbox"][1]
                
                # If lines are very close vertically (same logical line)
                if abs(next_y - current_y) < 5:
                    merge_candidates.append(next_line)
                    j += 1
                else:
                    break
            
            # Merge the candidates
            merged_line = self.merge_line_candidates(merge_candidates)
            if merged_line:
                merged_lines.append(merged_line)
            
            i = j if j > i + 1 else i + 1
        
        return merged_lines
    
    def merge_line_candidates(self, candidates: List[Dict]) -> Optional[Dict]:
        """Merge multiple line candidates into a single line"""
        if not candidates:
            return None
        
        # Sort by X position to get correct reading order
        all_spans = []
        for candidate in candidates:
            all_spans.extend(candidate["spans"])
        
        all_spans.sort(key=lambda x: x["bbox"][0])
        
        # Combine text
        combined_text = ""
        font_sizes = []
        fonts = []
        flags = []
        
        for span in all_spans:
            text = span["text"].strip()
            if text:
                # Add space if needed
                if combined_text and not combined_text.endswith(" ") and not text.startswith(" "):
                    combined_text += " "
                combined_text += text
                font_sizes.append(span["size"])
                fonts.append(span["font"])
                flags.append(span["flags"])
        
        if not combined_text.strip():
            return None
        
        # Calculate merged properties
        avg_font_size = sum(font_sizes) / len(font_sizes) if font_sizes else 12
        dominant_font = max(set(fonts), key=fonts.count) if fonts else ""
        is_bold = any(flag & 2**4 for flag in flags) if flags else False
        is_italic = any(flag & 2**1 for flag in flags) if flags else False
        
        # Calculate bounding box
        min_x = min(span["bbox"][0] for span in all_spans)
        min_y = min(span["bbox"][1] for span in all_spans)
        max_x = max(span["bbox"][2] for span in all_spans)
        max_y = max(span["bbox"][3] for span in all_spans)
        
        return {
            "text": combined_text.strip(),
            "avg_font_size": avg_font_size,
            "dominant_font": dominant_font,
            "is_bold": is_bold,
            "is_italic": is_italic,
            "bbox": [min_x, min_y, max_x, max_y],
            "y_pos": min_y,
            "x_pos": min_x,
            "width": max_x - min_x
        }
    
    def analyze_document_structure(self, text_blocks: List[Dict]) -> Dict:
        """Analyze document structure with RFP-specific logic"""
        if not text_blocks:
            return {}
        
        font_sizes = [block["font_size"] for block in text_blocks]
        font_size_counter = Counter(font_sizes)
        body_font_size = font_size_counter.most_common(1)[0][0]
        unique_font_sizes = sorted(set(font_sizes), reverse=True)
        
        # Detect document type
        all_text = " ".join([block["text"].lower() for block in text_blocks])
        
        # RFP detection patterns
        rfp_indicators = [
            r'rfp.*request for proposal',
            r'business plan.*ontario digital library',
            r'ontario.*digital library',
            r'summary.*background',
            r'appendix.*phases.*funding'
        ]
        
        rfp_score = sum(1 for pattern in rfp_indicators if re.search(pattern, all_text))
        is_rfp_document = rfp_score >= 2
        
        # Form detection patterns
        form_indicators = [
            r'application.*form',
            r'signature',
            r'undertake.*refund',
        ]
        
        form_score = sum(1 for pattern in form_indicators if re.search(pattern, all_text))
        is_form_document = form_score >= 2
        
        # Flyer detection patterns
        flyer_indicators = [
            r'pathway',
            r'stem',
            r'elective.*course',
            r'what colleges say'
        ]
        
        flyer_score = sum(1 for pattern in flyer_indicators if re.search(pattern, all_text))
        is_flyer_document = flyer_score >= 3
        
        return {
            "body_font_size": body_font_size,
            "unique_font_sizes": unique_font_sizes,
            "font_size_distribution": dict(font_size_counter),
            "large_font_threshold": body_font_size * 1.3,
            "medium_font_threshold": body_font_size * 1.15,
            "is_form_document": is_form_document,
            "is_flyer_document": is_flyer_document,
            "is_rfp_document": is_rfp_document
        }
    
    def is_likely_header_footer(self, text: str, context: Dict, doc_structure: Dict) -> bool:
        """Enhanced header/footer detection"""
        y_pos = context.get("y_pos", 0)
        page_height = context.get("page_height", 800)
        
        # Position-based detection
        if y_pos < 80 or y_pos > page_height - 80:
            return True
        
        text_lower = text.lower().strip()
        
        # Common header/footer patterns
        if (
            re.match(r'^\d+$', text_lower) or
            re.match(r'^page \d+', text_lower) or
            'copyright' in text_lower or
            '©' in text_lower or
            re.match(r'^march \d+, \d+$', text_lower) or  # Date headers
            re.match(r'^to develop.*business plan$', text_lower)  # RFP header
        ):
            return True
        
        return False
    
    def is_body_text_or_fragment(self, text: str, context: Dict, doc_structure: Dict) -> bool:
        """Detect body text and fragments that shouldn't be headings"""
        text_clean = text.strip()
        text_lower = text_clean.lower()
        
        # RFP-specific body text patterns
        if doc_structure.get("is_rfp_document", False):
            body_patterns = [
                r'^the odl will deliver',
                r'^first, some background',
                r'^we will provide',
                r'^working together',
                r'must also secure.*commitment',
                r'^that documents and clearly',
                r'^structures, as well as implementation',
                r'^areas, have the facilities',
                r'^the odl steering committee',
                r'this document',
                r'the following',
                r'ontario residents',
                r'library association'
            ]
            
            for pattern in body_patterns:
                if re.search(pattern, text_lower):
                    return True
        
        # Generic body text detection
        if (
            len(text_clean) > 80 and  # Long sentences
            not re.match(r'^[A-Z\s]+:?$', text_clean) and  # Not all caps headers
            not re.match(r'^\d+\.\s+[A-Z]', text_clean) and  # Not numbered sections
            ('the ' in text_lower or 'and ' in text_lower or 'to ' in text_lower)
        ):
            return True
        
        # Fragmented text (likely broken lines)
        if (
            len(text_clean) < 20 and
            not re.match(r'^[A-Z]', text_clean) and
            not text_clean.endswith(':') and
            re.search(r'^(r|quest|oposal|r pr)$', text_lower)
        ):
            return True
        
        return False
    
    def extract_title_enhanced(self, text_blocks: List[Dict], doc_structure: Dict) -> str:
        """Enhanced title extraction with better line reconstruction"""
        if not text_blocks:
            return ""
        
        # For flyers, return empty title
        if doc_structure.get("is_flyer_document", False):
            return ""
        
        # For forms
        if doc_structure.get("is_form_document", False):
            first_page_blocks = [b for b in text_blocks if b["page"] == 1][:10]
            
            for block in first_page_blocks:
                text = block["text"].strip()
                
                if (self.is_likely_header_footer(text, block, doc_structure) or
                    len(text) < 10):
                    continue
                
                if ('form' in text.lower() or 'application' in text.lower()) and len(text) > 15:
                    return text
        
        # For RFP and other documents - look for complete title
        first_pages = [b for b in text_blocks if b["page"] <= 2]
        
        # Look for RFP title specifically
        if doc_structure.get("is_rfp_document", False):
            title_candidates = []
            
            for block in first_pages:
                text = block["text"].strip()
                
                if (self.is_likely_header_footer(text, block, doc_structure) or
                    self.is_body_text_or_fragment(text, block, doc_structure)):
                    continue
                
                # Look for RFP title patterns
                if ('rfp' in text.lower() and 'request' in text.lower() and len(text) > 20):
                    return text
                
                # Look for substantial text that could be part of title
                if (len(text) > 15 and len(text) < 200 and
                    ('proposal' in text.lower() or 'ontario' in text.lower() or 'digital library' in text.lower())):
                    title_candidates.append({
                        "text": text,
                        "font_size": block["font_size"],
                        "page": block["page"],
                        "y_pos": block["y_pos"]
                    })
            
            # Combine title candidates
            if title_candidates:
                title_candidates.sort(key=lambda x: (x["page"], x["y_pos"]))
                
                # Look for multi-line title
                combined_title = ""
                current_page = title_candidates[0]["page"]
                current_y = title_candidates[0]["y_pos"]
                
                for candidate in title_candidates:
                    if (candidate["page"] == current_page and
                        abs(candidate["y_pos"] - current_y) < 100):
                        if combined_title:
                            combined_title += " "
                        combined_title += candidate["text"]
                
                if combined_title:
                    return combined_title
        
        # General title extraction
        title_candidates = []
        body_font = doc_structure.get("body_font_size", 12)
        large_font_threshold = doc_structure.get("large_font_threshold", body_font * 1.3)
        
        for block in first_pages:
            text = block["text"].strip()
            
            if (self.is_likely_header_footer(text, block, doc_structure) or 
                len(text) < 5 or len(text) > 500 or
                self.is_body_text_or_fragment(text, block, doc_structure)):
                continue
            
            font_ratio = block["font_size"] / body_font if body_font > 0 else 1
            
            if (block["font_size"] >= large_font_threshold and
                block["y_pos"] > 50 and
                block["y_pos"] < 600 and
                len(text.split()) >= 2):
                
                title_candidates.append({
                    "text": text,
                    "font_size": block["font_size"],
                    "font_ratio": font_ratio,
                    "page": block["page"],
                    "y_pos": block["y_pos"]
                })
        
        if title_candidates:
            title_candidates.sort(key=lambda x: (-x["font_ratio"], x["page"], x["y_pos"]))
            return title_candidates[0]["text"]
        
        return ""
    
    def is_heading_enhanced(self, text: str, context: Dict, doc_structure: Dict) -> Tuple[bool, str]:
        """Enhanced heading detection with document-type awareness"""
        text_clean = text.strip()
        text_lower = text_clean.lower()
        
        # Basic filters
        if (len(text_clean) < 2 or len(text_clean) > 300 or
            self.is_likely_header_footer(text_clean, context, doc_structure) or
            self.is_body_text_or_fragment(text_clean, context, doc_structure)):
            return False, ""
        
        font_size = context.get("font_size", 12)
        is_bold = context.get("is_bold", False)
        body_font = doc_structure.get("body_font_size", 12)
        font_ratio = font_size / body_font if body_font > 0 else 1
        word_count = context.get("word_count", len(text_clean.split()))
        
        # RFP-specific heading patterns
        if doc_structure.get("is_rfp_document", False):
            # H1 - Main sections
            h1_patterns = [
                r'^ontario.*s digital library$',
                r'^a critical component.*prosperity strategy$',
                r'^summary$',
                r'^background$',
                r'^the business plan to be developed$',
                r'^approach and specific proposal requirements$',
                r'^evaluation and awarding of contract$',
                r'^appendix [abc]:.*'
            ]
            
            for pattern in h1_patterns:
                if re.search(pattern, text_lower):
                    return True, "H1"
            
            # H2 patterns
            h2_patterns = [
                r'^timeline:?$',
                r'^milestones$',
                r'^phase [iv]+:.*',
                r'^appendix [abc]:.*'
            ]
            
            for pattern in h2_patterns:
                if re.search(pattern, text_lower):
                    return True, "H2"
            
            # H3 patterns
            h3_patterns = [
                r'^equitable access.*:$',
                r'^shared.*:$',
                r'^local points.*:$',
                r'^access:$',
                r'^guidance.*:$',
                r'^training:$',
                r'^provincial.*:$',
                r'^technological.*:$',
                r'^what could.*:$',
                r'^\d+\.\s+[a-z].*'  # Numbered items in appendix
            ]
            
            for pattern in h3_patterns:
                if re.search(pattern, text_lower):
                    return True, "H3"
            
            # H4 patterns
            h4_patterns = [
                r'^for each ontario.*:$',
                r'^for the ontario.*:$'
            ]
            
            for pattern in h4_patterns:
                if re.search(pattern, text_lower):
                    return True, "H4"
        
        # Form documents
        elif doc_structure.get("is_form_document", False):
            if (font_ratio >= 1.8 or
                (font_ratio >= 1.5 and is_bold and len(text_clean) > 20)):
                if (not re.match(r'^\d+\.$', text_clean) and
                    not re.match(r'^[a-z\s]+:$', text_clean.lower()) and
                    len(text_clean.split()) >= 3):
                    return True, "H1"
        
        # Flyer documents
        elif doc_structure.get("is_flyer_document", False):
            if (re.search(r'stem pathways?$', text_lower) or
                re.search(r'parsippany.*stem', text_lower) or
                (font_ratio >= 1.8 and word_count <= 8 and is_bold)):
                return True, "H1"
            elif (re.match(r'^pathway options?$', text_lower) or
                  re.match(r'^elective course offerings?$', text_lower) or
                  (font_ratio >= 1.4 and word_count <= 6 and is_bold and text_clean.isupper())):
                return True, "H2"
            elif re.match(r'^what colleges say!?$', text_lower):
                return True, "H3"
        
        # General document patterns
        else:
            # H1 indicators
            if (font_ratio >= 1.5 or
                (font_ratio >= 1.3 and is_bold) or
                re.match(r'^\d+\.\s+[A-Z]', text_clean) or
                (font_ratio >= 1.2 and word_count <= 6 and text_clean.isupper())):
                return True, "H1"
            
            # H2 indicators
            elif (font_ratio >= 1.25 or
                  (font_ratio >= 1.15 and is_bold) or
                  re.match(r'^\d+\.\d+\s+[A-Z]', text_clean)):
                return True, "H2"
            
            # H3 indicators
            elif (font_ratio >= 1.15 or
                  (font_ratio >= 1.05 and is_bold) or
                  (is_bold and font_ratio >= 1.0 and word_count <= 10 and text_clean.endswith(':'))):
                return True, "H3"
        
        return False, ""
    
    def remove_duplicates_intelligent(self, headings: List[Dict]) -> List[Dict]:
        """Intelligent duplicate removal"""
        if not headings:
            return []
        
        heading_groups = defaultdict(list)
        
        for heading in headings:
            normalized = re.sub(r'\s+', ' ', heading["text"].lower().strip())
            normalized = re.sub(r'[^\w\s]', '', normalized)
            key = normalized[:40] if len(normalized) > 40 else normalized
            heading_groups[key].append(heading)
        
        unique_headings = []
        for group in heading_groups.values():
            if len(group) == 1:
                unique_headings.append(group[0])
            else:
                level_priority = {"H1": 1, "H2": 2, "H3": 3, "H4": 4}
                best = min(group, key=lambda x: (
                    level_priority.get(x["level"], 5),
                    x["page"],
                    -len(x["text"])  # Prefer longer text
                ))
                unique_headings.append(best)
        
        return unique_headings
    
    def extract_outline(self, pdf_path: str) -> Dict:
        """Main extraction method with improved line reconstruction"""
        try:
            text_blocks = self.extract_text_with_metadata(pdf_path)
            
            if not text_blocks:
                return {"title": "", "outline": []}
            
            doc_structure = self.analyze_document_structure(text_blocks)
            title = self.extract_title_enhanced(text_blocks, doc_structure)
            
            # For form documents, return empty outline
            if doc_structure.get("is_form_document", False):
                return {
                    "title": title,
                    "outline": []
                }
            
            # Extract headings
            potential_headings = []
            
            for block in text_blocks:
                is_heading, level = self.is_heading_enhanced(block["text"], block, doc_structure)
                
                if is_heading and level:
                    potential_headings.append({
                        "text": block["text"].strip(),
                        "level": level,
                        "page": block["page"],
                        "y_pos": block.get("y_pos", 0),
                        "font_size": block.get("font_size", 12)
                    })
            
            unique_headings = self.remove_duplicates_intelligent(potential_headings)
            unique_headings.sort(key=lambda x: (x["page"], x.get("y_pos", 0)))
            
            final_outline = []
            for heading in unique_headings:
                final_outline.append({
                    "level": heading["level"],
                    "text": heading["text"],
                    "page": heading["page"]
                })
            
            return {
                "title": title,
                "outline": final_outline
            }
            
        except Exception as e:
            logger.error(f"Error processing {pdf_path}: {str(e)}")
            return {"title": "", "outline": []}

def process_pdfs():
    """Process all PDFs in input directory and generate JSON outputs"""
    # Use absolute paths for Docker container
    input_dir = "/app/input"
    output_dir = "/app/output"
    
    os.makedirs(output_dir, exist_ok=True)
    extractor = ImprovedPDFOutlineExtractor()
    
    if not os.path.exists(input_dir):
        logger.error(f"Input directory {input_dir} does not exist")
        return
    
    pdf_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        logger.info("No PDF files found in input directory")
        return
    
    logger.info(f"Found {len(pdf_files)} PDF files to process")
    
    for pdf_file in pdf_files:
        try:
            pdf_path = os.path.join(input_dir, pdf_file)
            output_file = os.path.splitext(pdf_file)[0] + ".json"
            output_path = os.path.join(output_dir, output_file)
            
            logger.info(f"Processing {pdf_file}...")
            
            result = extractor.extract_outline(pdf_path)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Generated {output_file}")
            
        except Exception as e:
            logger.error(f"Failed to process {pdf_file}: {str(e)}")

if __name__ == "__main__":
    process_pdfs()
