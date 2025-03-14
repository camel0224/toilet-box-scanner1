import streamlit as st
import cv2
import pandas as pd
from datetime import datetime
import os
from PIL import Image
import numpy as np
import io
import requests
from bs4 import BeautifulSoup
import asyncio
import aiohttp
from pyzbar.pyzbar import decode
import av
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase, WebRtcMode, RTCConfiguration

# Set page config
st.set_page_config(page_title="Toilet Box Scanner", layout="wide")

# Initialize session state
if 'inventory_data' not in st.session_state:
    st.session_state.inventory_data = pd.DataFrame(
        columns=['Date', 'Barcode', 'Brand', 'Model', 'Quantity', 'Notes',
                'Ferguson Price', 'Ferguson Link', 'Product Description']
    )

if 'last_barcode' not in st.session_state:
    st.session_state.last_barcode = None

class BarcodeVideoTransformer(VideoTransformerBase):
    def __init__(self):
        self.last_barcode = None
        self.frame_count = 0
        self.last_detection_time = 0

    def transform(self, frame):
        self.frame_count += 1
        img = frame.to_ndarray(format="bgr24")
        
        # Process every 3rd frame for performance
        if self.frame_count % 3 != 0:
            return img
        
        # Enhance image for better barcode detection
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # Detect barcodes
        barcodes = decode(gray)
        
        # Draw rectangle around barcode and show data
        for barcode in barcodes:
            # Extract barcode data
            barcode_data = barcode.data.decode('utf-8')
            
            # Draw rectangle with thicker lines
            points = np.array([barcode.polygon], np.int32)
            cv2.polylines(img, [points], True, (0, 255, 0), 3)
            
            # Add background rectangle for text
            cv2.rectangle(img, 
                        (barcode.rect.left, barcode.rect.top - 30),
                        (barcode.rect.left + 200, barcode.rect.top),
                        (0, 255, 0),
                        cv2.FILLED)
            
            # Put text with better visibility
            cv2.putText(img, barcode_data,
                       (barcode.rect.left, barcode.rect.top - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
            
            # Store the barcode
            if barcode_data != self.last_barcode:
                self.last_barcode = barcode_data
                st.session_state.last_barcode = barcode_data
        
        # Add scanning overlay
        height, width = img.shape[:2]
        overlay = img.copy()
        
        # Draw scanning lines
        scan_line_y = (self.frame_count * 5) % height
        cv2.line(overlay, (0, scan_line_y), (width, scan_line_y), (0, 255, 0), 2)
        
        # Add the overlay
        cv2.addWeighted(overlay, 0.3, img, 0.7, 0, img)
        
        return img

async def search_ferguson(barcode):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }
    
    # First try direct product lookup
    direct_url = f'https://www.ferguson.com/product/{barcode}'
    search_url = f'https://www.ferguson.com/search/{barcode}'
    
    results = {
        'Ferguson Price': 'N/A',
        'Ferguson Link': '',
        'Product Description': '',
        'Brand': '',
        'Model': ''
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            # Try direct product page first
            async with session.get(direct_url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    results['Ferguson Link'] = direct_url
                    
                    # Get product details
                    product_title = soup.find('h1', {'class': 'product-title'})
                    if product_title:
                        results['Product Description'] = product_title.text.strip()
                    
                    # Get price
                    price_elem = soup.find('span', {'class': 'product-price'})
                    if price_elem:
                        results['Ferguson Price'] = price_elem.text.strip()
                    
                    # Get brand
                    brand_elem = soup.find('span', {'class': 'product-brand'})
                    if brand_elem:
                        results['Brand'] = brand_elem.text.strip()
                        
                    # Get model
                    model_elem = soup.find('span', {'class': 'product-model'})
                    if model_elem:
                        results['Model'] = model_elem.text.strip()
                
                # If direct lookup fails, try search page
                else:
                    async with session.get(search_url, headers=headers, timeout=30) as search_response:
                        if search_response.status == 200:
                            html = await search_response.text()
                            soup = BeautifulSoup(html, 'html.parser')
                            
                            # Find first product link
                            product_link = soup.find('a', {'class': 'product-link'})
                            if product_link and 'href' in product_link.attrs:
                                product_url = f"https://www.ferguson.com{product_link['href']}"
                                results['Ferguson Link'] = product_url
                                
                                # Get product details from search result
                                product_title = product_link.find('h3')
                                if product_title:
                                    results['Product Description'] = product_title.text.strip()
                                
                                price_elem = product_link.find('span', {'class': 'price'})
                                if price_elem:
                                    results['Ferguson Price'] = price_elem.text.strip()
    
    except Exception as e:
        st.error(f"Error searching Ferguson: {str(e)}")
    
    return results

# Title
st.title("Toilet Box Scanner")

# Tabs
tab1, tab2 = st.tabs(["Scan Item", "View Inventory"])

with tab1:
    st.header("Scan New Item")
    
    # Add instructions
    st.markdown("""
    ### Instructions:
    1. Allow camera access when prompted
    2. Hold the barcode steady in front of the camera
    3. Wait for the green box to appear around the barcode
    4. Once detected, click 'Fetch Product Details'
    """)
    
    # Configure WebRTC for better performance
    rtc_config = RTCConfiguration(
        {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
    )
    
    # Add the webcam component with larger size
    col1, col2 = st.columns([3, 1])
    with col1:
        webrtc_ctx = webrtc_streamer(
            key="barcode-scanner",
            mode=WebRtcMode.SENDRECV,
            rtc_configuration=rtc_config,
            video_transformer_factory=BarcodeVideoTransformer,
            async_transform=True,
            media_stream_constraints={"video": {"width": 1280, "height": 720}},
        )
    
    # If a barcode is detected
    if st.session_state.last_barcode:
        st.write("Detected Barcode:", st.session_state.last_barcode)
        
        # Form for additional details
        with st.form("inventory_form"):
            if st.form_submit_button("Fetch Product Details"):
                with st.spinner('Searching Ferguson...'):
                    results = asyncio.run(search_ferguson(st.session_state.last_barcode))
                    
                    brand = st.text_input("Brand", value=results['Brand'])
                    model = st.text_input("Model", value=results['Model'])
                    quantity = st.number_input("Quantity", min_value=1, value=1)
                    notes = st.text_area("Notes")
                    
                    # Add to inventory
                    new_row = {
                        'Date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'Barcode': st.session_state.last_barcode,
                        'Brand': brand,
                        'Model': model,
                        'Quantity': quantity,
                        'Notes': notes,
                        'Ferguson Price': results['Ferguson Price'],
                        'Ferguson Link': results['Ferguson Link'],
                        'Product Description': results['Product Description']
                    }
                    
                    st.session_state.inventory_data = pd.concat([
                        st.session_state.inventory_data,
                        pd.DataFrame([new_row])
                    ], ignore_index=True)
                    
                    st.success("Item added to inventory!")
                    
                    # Show product link
                    if results['Ferguson Link']:
                        st.markdown(f"[View Product on Ferguson]({results['Ferguson Link']})")
                    
                    st.session_state.last_barcode = None
                    st.experimental_rerun()

with tab2:
    st.header("Current Inventory")
    
    # Download button for inventory
    if not st.session_state.inventory_data.empty:
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            st.session_state.inventory_data.to_excel(writer, index=False)
        
        excel_data = excel_buffer.getvalue()
        st.download_button(
            label="Download Inventory as Excel",
            data=excel_data,
            file_name=f"toilet_inventory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    # Display inventory table
    if st.session_state.inventory_data.empty:
        st.info("No items in inventory yet. Add items using the 'Scan Item' tab.")
    else:
        # Add filters
        col1, col2 = st.columns(2)
        with col1:
            brand_filter = st.multiselect(
                "Filter by Brand",
                options=st.session_state.inventory_data['Brand'].unique(),
                default=[]
            )
        with col2:
            model_filter = st.text_input("Search by Model")
        
        # Apply filters
        filtered_df = st.session_state.inventory_data.copy()
        if brand_filter:
            filtered_df = filtered_df[filtered_df['Brand'].isin(brand_filter)]
        if model_filter:
            filtered_df = filtered_df[filtered_df['Model'].str.contains(model_filter, case=False, na=False)]
        
        # Display the filtered table
        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True
        )
        
        # Display summary statistics
        st.subheader("Inventory Summary")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Items", filtered_df['Quantity'].sum())
        with col2:
            st.metric("Unique Models", len(filtered_df))
        with col3:
            st.metric("Brands", len(filtered_df['Brand'].unique()))
