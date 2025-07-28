import os
import json
import re
import fitz
import pandas as pd
from glob import glob
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed


class OutlineExtractor:
    def __init__(self):
        pass

    def _get_line_properties(self, doc):
        lines_data = []
        all_font_sizes = []

        for page in doc:
            blocks = page.get_text("dict")["blocks"]
            for block in blocks:
                if block['type'] == 0:
                    for line in block['lines']:
                        for span in line['spans']:
                            all_font_sizes.append(round(span['size']))

        if not all_font_sizes:
            return pd.DataFrame()

        body_size = Counter(all_font_sizes).most_common(1)[0][0]

        for page_num, page in enumerate(doc):
            blocks = page.get_text("dict")["blocks"]
            prev_line_y1 = 0

            for block in blocks:
                if block['type'] == 0:
                    for line in block['lines']:
                        line_text = " ".join([span['text'] for span in line['spans']]).strip()
                        if not line_text or not line['spans']:
                            continue

                        span = line['spans'][0]
                        font_size = round(span['size'])
                        font_name = span['font']
                        is_bold = 'bold' in font_name.lower() or span.get('flags', 0) & 2**4

                        line_bbox = line['bbox']
                        space_above = line_bbox[1] - prev_line_y1

                        score = 0
                        if font_size > body_size:
                            score += (font_size - body_size)
                        if is_bold:
                            score += body_size * 0.5
                        if bool(re.match(r'^\s*(\d+(\.\d+)*|[A-Za-z][\.\)])\s+', line_text)):
                            score += body_size * 0.7
                        if len(line_text) < 100:
                            score += 1

                        lines_data.append({
                            'text': line_text,
                            'font_size': font_size,
                            'is_bold': is_bold,
                            'indentation': line_bbox,
                            'page': page_num + 1,
                            'score': score,
                            'y0': line_bbox[1]
                        })
                        prev_line_y1 = line_bbox[2]

        return pd.DataFrame(lines_data)

    def _build_hierarchy(self, lines_df):
        if lines_df.empty:
            return "Untitled Document", []

        min_score_threshold = lines_df['score'].quantile(0.90)
        headings_df = lines_df[lines_df['score'] > min_score_threshold].copy()

        if headings_df.empty:
            return "Untitled Document (No Headings Found)", []

        headings_df.sort_values(by=['page', 'y0'], inplace=True)
        doc_title_row = headings_df.iloc[0]
        doc_title = doc_title_row['text']
        headings_df = headings_df.iloc[1:]

        heading_font_sizes = sorted(headings_df['font_size'].unique(), reverse=True)
        size_to_level = {size: f"H{i+1}" for i, size in enumerate(heading_font_sizes[:3])}

        outline = []
        for _, h in headings_df.iterrows():
            level = size_to_level.get(h['font_size'])
            if level:
                outline.append({
                    "level": level,
                    "text": h['text'],
                    "page": h['page']
                })

        return doc_title, outline

    def extract_outline(self, pdf_path):
        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            print(f"Error opening PDF {pdf_path}: {e}")
            return {"title": f"Error processing {os.path.basename(pdf_path)}", "outline": []}

        lines_df = self._get_line_properties(doc)
        if lines_df.empty:
            return {"title": "Empty or Unreadable Document", "outline": []}

        title, outline = self._build_hierarchy(lines_df)
        return {"title": title, "outline": outline}


def process_pdf(pdf_path, output_dir):
    extractor = OutlineExtractor()
    output_filename = os.path.basename(pdf_path).replace('.pdf', '.json')
    output_path = os.path.join(output_dir, output_filename)

    try:
        outline_data = extractor.extract_outline(pdf_path)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(outline_data, f, indent=4, ensure_ascii=False)
        return f"✅ {os.path.basename(pdf_path)} processed."
    except Exception as e:
        return f"❌ Failed: {os.path.basename(pdf_path)} — {e}"


def run_challenge():
    input_dir = '/app/input'
    output_dir = '/app/output'

    if not os.path.exists(input_dir):
        input_dir = 'input'
        output_dir = 'output'

    os.makedirs(output_dir, exist_ok=True)

    pdf_files = glob(os.path.join(input_dir, '*.pdf'))
    if not pdf_files:
        print("No PDF files found in the input directory.")
        return

    print(f"Found {len(pdf_files)} PDF(s). Starting parallel processing...")

    results = []
    with ProcessPoolExecutor() as executor:
        futures = [executor.submit(process_pdf, pdf, output_dir) for pdf in pdf_files]
        for future in as_completed(futures):
            results.append(future.result())

    for res in results:
        print(res)


if __name__ == "__main__":
    run_challenge()

