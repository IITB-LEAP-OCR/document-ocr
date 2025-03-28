import json
import base64
import os
from pathlib import Path
import xml.dom.minidom
import re
from bs4 import BeautifulSoup  # Required for parsing table HTML

from config import *

def remove_polygon(block):
    if 'polygon' in block:
        del block['polygon']
    
    # Convert bbox values to integers if present
    if 'bbox' in block and isinstance(block['bbox'], list):
        block['bbox'] = [int(value) for value in block['bbox']]
    
    if 'children' in block and block['children']:
        for child in block['children']:
            remove_polygon(child)

def extract_data(input_json_file):
    with open(input_json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Remove Polygon from data and convert bbox to integers
    if 'children' in data:
        for block in data.get('children', []):
            remove_polygon(block)
    else:
        remove_polygon(data)

    return data

def clean_html_content(html):
    """
    Remove all block_type and block-type attributes from HTML content,
    along with similar variations that might appear in the data.
    """
    if not html:
        return ""
    
    # Create a combined pattern to match both block_type and block-type attributes
    # This will handle various spacing and quote styles
    patterns = [
        r'block_type\s*=\s*(["\']?)[\w-]+\1',  # block_type="value"
        r'block-type\s*=\s*(["\']?)[\w-]+\1',  # block-type="value"
        r'blocktype\s*=\s*(["\']?)[\w-]+\1',   # blocktype="value"
        r'type\s*=\s*(["\']?)block[\w-]*\1',   # type="block" or type="block-item"
    ]
    
    cleaned = html
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned)
    
    # Specific handling for <li> tags with block-type attributes
    # This pattern will match <li block-type="ListItem"> and similar variations
    cleaned = re.sub(r'<li\s+[^>]*?block[-_]type\s*=\s*(["\']?)[\w-]+\1[^>]*?>', '<li>', cleaned)
    
    # Clean up any empty attributes that might be left after removal
    cleaned = re.sub(r'\s+>', '>', cleaned)
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    
    return cleaned

def process_table_cells(block_children):
    """
    Extract coordinate information from TableCell children to enhance OTSL table
    
    Args:
        block_children: List of child blocks (TableCell elements)
        
    Returns:
        dict: Mapping of cell positions to their coordinates
    """
    if not block_children:
        return {}
    
    cell_coordinates = {}
    row_idx = 0
    cell_idx = 0
    prev_y1 = None
    
    # Sort cells by y1 (vertical position) then x1 (horizontal position)
    sorted_cells = sorted(block_children, key=lambda cell: (
        cell.get('bbox', [0, 0, 0, 0])[1],  # y1 (primary sort)
        cell.get('bbox', [0, 0, 0, 0])[0]   # x1 (secondary sort)
    ))
    
    for cell in sorted_cells:
        if not cell.get('block_type') == 'TableCell':
            continue
        
        bbox = cell.get('bbox', [0, 0, 0, 0])
        if len(bbox) < 4:
            continue
            
        x1, y1, x2, y2 = bbox
        
        # If this is a new row (different y1 from previous cell)
        if prev_y1 is None or abs(y1 - prev_y1) > 5:  # Allow small tolerance for alignment
            row_idx += 1
            cell_idx = 0
            prev_y1 = y1
        
        cell_idx += 1
        cell_coordinates[(row_idx, cell_idx)] = {
            'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2,
            'html': clean_html_content(cell.get('html', ''))
        }
    
    return cell_coordinates

def convert_table_to_otsl(html_content, bbox):
    """
    Convert table HTML content to OTSL representation.
    
    OTSL format uses:
    - <fcell> for non-empty cells
    - <ecell> for empty cells
    - <ched> for column header cells
    - <rhed> for row header cells
    - <srow> for table sections
    """
    if not html_content or "<table" not in html_content:
        return html_content
    
    try:
        # Parse the HTML content
        soup = BeautifulSoup(html_content, 'html.parser')
        table = soup.find('table')
        
        if not table:
            return html_content
        
        # Start building OTSL table representation
        otsl_table = ""
        
        # Extract rows
        rows = table.find_all('tr')
        is_header_row = True  # Assume first row is header
        
        for row_idx, row in enumerate(rows):
            # otsl_table += f"  <tr id=\"row_{row_idx}\">\n"
            
            # Extract cells (th and td)
            cells = row.find_all(['th', 'td'])
            for cell_idx, cell in enumerate(cells):
                # Get cell content
                cell_content = cell.get_text().strip()
                cell_type = cell.name
                
                # Determine OTSL cell type
                if not cell_content:
                    # Empty cell
                    otsl_cell_type = "ecel"
                elif cell_type == "th" or (is_header_row and cell_idx == 0):
                    # Header cell (either th or first cell in first row for row headers)
                    otsl_cell_type = "ched" if cell_idx > 0 or row_idx == 0 else "rhed"
                else:
                    # Regular non-empty cell
                    otsl_cell_type = "fcel"
                
                # Create OTSL cell with proper attributes
                otsl_table += f"    <{otsl_cell_type}>{cell_content}</{otsl_cell_type}>\n"
            
            otsl_table += "<ncel></ncel>\n"
            is_header_row = False  # Only first row is treated as header
        
        # otsl_table += "</table>"
        return otsl_table
    
    except Exception as e:
        print(f"Error converting table to OTSL: {str(e)}")
        return html_content  # Return original content if conversion fails

def convert_to_tags(block):
    """Convert a block to tag-based format"""
    block_type = block.get('block_type', 'div')
    bbox = block.get('bbox', [0, 0, 0, 0])
    html_content = block.get('html', '')
    children = block.get('children', [])
    
    # Clean the HTML content to remove block_type attributes
    html_content = clean_html_content(html_content)
    
    # Special handling for tables if this is a Table block
    if block_type == 'Table':
        html_content = convert_table_to_otsl(html_content, bbox)
        # We'll skip processing TableCell children separately since they're already in the table
    
    # Create location tags with proper x/y naming
    # Create location tags with proper x/y naming
    if len(bbox) >= 4:
        loc_tags = f'<loc_{bbox[0]}><loc_{bbox[1]}><loc_{bbox[2]}><loc_{bbox[3]}>'
    else:
        loc_tags = '<loc_0><loc_0><loc_0><loc_0>'
    
    # Start the tag
    result = f'<{block_type}>\n  {loc_tags}\n'
    
    # Add the HTML content
    if html_content:
        # Indent HTML content for better readability
        result += f"  {html_content}\n"
    
    # Process children if they exist
    if 'children' in block and block['children']:
        # Skip TableCell children for Table blocks since they're handled in the table conversion
        if block_type == 'Table':
            child_blocks = [child for child in children if child.get('block_type') != 'TableCell']
        else:
            child_blocks = children
            
        for child in child_blocks:
            # Indent child content
            child_content = convert_to_tags(child)
            indented_child_content = "  " + child_content.replace("\n", "\n  ")
            result += f"{indented_child_content}\n"
    
    # Close the tag
    result += f'</{block_type}>'
    
    return result

def json_to_tags(data):
    """Convert entire JSON structure to tags format"""
    result = '<?xml version="1.0" encoding="UTF-8"?>\n<document>\n'
    
    if 'children' in data:
        for block in data['children']:
            result += convert_to_tags(block)
    else:
        result += convert_to_tags(data)
    
    result += '\n</document>'
    return result

def beautify_xml(xml_string):
    parsed_xml = xml.dom.minidom.parseString(xml_string)
    return parsed_xml.toprettyxml(indent="  ") 

def main():
    if not os.path.exists(INPUT_JSON_FILE):
        os.system(f"marker_single {INPUT_FILE} --output_dir {OUTPUT_DIR} --output_format {OUTPUT_FORMAT} --languages {LANGUAGES}")
      
    # Extract the data
    data = extract_data(INPUT_JSON_FILE)
    
    # Convert to tags format
    tags_output = json_to_tags(data)
    
    # Save the tag-based output to a new file
    output_tags_file = os.path.splitext(OUTPUT_JSON_FILE)[0] + '.xml'
    with open(output_tags_file, 'w', encoding='utf-8') as f:
        f.write(tags_output)
    
    # Also save the processed JSON for reference
    with open(OUTPUT_JSON_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    
    print(f"Processed {INPUT_JSON_FILE}")
    print(f"Removed all polygon keys and converted bbox values to integers")
    print(f"Converted tables to OTSL format with proper coordinates")
    print(f"JSON output saved to {OUTPUT_JSON_FILE}")
    print(f"Tag-based output saved to {output_tags_file}")


if __name__ == "__main__":
    main()
