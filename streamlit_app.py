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
from streamlit_webrtc import webrtc_streamer, VideoTransformerBase, WebRtcMode

# Set page config
st.set_page_config(page_title="Toilet Box Scanner", layout="wide")

# Initialize session state
if 'inventory_data' not in st.session_state:
    st.session_state.inventory_data = pd.DataFrame(
        columns=['Date', 'Model Number', 'Brand', 'Quantity', 'Notes',
                'Home Depot Price', 'Home Depot Link',
                'Lowes Price', 'Lowes Link']
    )

if 'last_barcode' not in st.session_state:
    st.session_state.last_barcode = None

class BarcodeVideoTransformer(VideoTransformerBase):
    def __init__(self):
        self.last_barcode = None

    def transform(self, frame):
        img = frame.to_ndarray(format="bgr24")
        
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Detect barcodes
        barcodes = decode(gray)
        
        # Draw rectangle around barcode and show data
        for barcode in barcodes:
            # Extract barcode data
            barcode_data = barcode.data.decode('utf-8')
            
            # Draw rectangle
            points = np.array([barcode.polygon], np.int32)
            cv2.polylines(img, [points], True, (0, 255, 0), 2)
            
            # Put text
            cv2.putText(img, barcode_data, (barcode.rect.left, barcode.rect.top - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            
            # Store the barcode
            if barcode_data != self.last_barcode:
                self.last_barcode = barcode_data
                st.session_state.last_barcode = barcode_data
        
        return img

async def search_product_prices(search_term):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
    }
    
    # Search URLs
    urls = {
        'homedepot': f'https://www.homedepot.com/s/{search_term}',
        'lowes': f'https://www.lowes.com/search?searchTerm={search_term}'
    }
    
    results = {
        'Home Depot Price': 'N/A',
        'Home Depot Link': '',
        'Lowes Price': 'N/A',
        'Lowes Link': '',
        'Product Name': '',
        'Brand': ''
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            for retailer, url in urls.items():
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        if retailer == 'homedepot':
                            results['Home Depot Link'] = url
                            price_elem = soup.find('span', {'class': 'price-format__main-price'})
                            if price_elem:
                                results['Home Depot Price'] = price_elem.text.strip()
                            
                            # Try to get product name and brand
                            product_elem = soup.find('h1', {'class': 'product-title__title'})
                            if product_elem:
                                results['Product Name'] = product_elem.text.strip()
                                brand_elem = soup.find('span', {'class': 'product-title__brand'})
                                if brand_elem:
                                    results['Brand'] = brand_elem.text.strip()
                        
                        elif retailer == 'lowes':
                            results['Lowes Link'] = url
                            price_elem = soup.find('span', {'class': 'main-price'})
                            if price_elem:
                                results['Lowes Price'] = price_elem.text.strip()
    except Exception as e:
        st.error(f"Error searching prices: {str(e)}")
    
    return results

# Title
st.title("Toilet Box Scanner")

# Tabs
tab1, tab2, tab3 = st.tabs(["Scan with Camera", "Manual Entry", "View Inventory"])

# Tab 1: Camera Scanner
with tab1:
    st.header("Scan with Camera")
    
    # Add the webcam component
    webrtc_ctx = webrtc_streamer(
        key="barcode-scanner",
        mode=WebRtcMode.SENDRECV,
        video_transformer_factory=BarcodeVideoTransformer,
        async_transform=True,
    )
    
    # If a barcode is detected
    if st.session_state.last_barcode:
        st.write("Detected Barcode:", st.session_state.last_barcode)
        
        # Form for additional details
        with st.form("camera_form"):
            if st.form_submit_button("Fetch Product Details"):
                with st.spinner('Searching...'):
                    prices = asyncio.run(search_product_prices(st.session_state.last_barcode))
                    
                    brand = st.text_input("Brand", value=prices['Brand'])
                    model = st.text_input("Model Number", value=st.session_state.last_barcode)
                    quantity = st.number_input("Quantity", min_value=1, value=1)
                    notes = st.text_area("Notes")
                    
                    # Add to inventory
                    new_row = {
                        'Date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        'Model Number': model,
                        'Brand': brand,
                        'Quantity': quantity,
                        'Notes': notes,
                        'Home Depot Price': prices['Home Depot Price'],
                        'Home Depot Link': prices['Home Depot Link'],
                        'Lowes Price': prices['Lowes Price'],
                        'Lowes Link': prices['Lowes Link']
                    }
                    
                    st.session_state.inventory_data = pd.concat([
                        st.session_state.inventory_data,
                        pd.DataFrame([new_row])
                    ], ignore_index=True)
                    
                    st.success("Item added to inventory!")
                    st.session_state.last_barcode = None
                    st.experimental_rerun()

# Tab 2: Manual Entry
with tab2:
    st.header("Manual Entry")
    
    # Manual entry form
    with st.form("manual_form"):
        model_number = st.text_input("Model Number")
        brand = st.selectbox("Brand", ["Kohler", "TOTO", "American Standard", "Other"])
        quantity = st.number_input("Quantity", min_value=1, value=1)
        notes = st.text_area("Notes")
        
        submit_button = st.form_submit_button("Add to Inventory")
        
        if submit_button and model_number:
            with st.spinner('Searching for prices...'):
                # Get prices from retailers
                prices = asyncio.run(search_product_prices(model_number))
                
                # Add to inventory
                new_row = {
                    'Date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'Model Number': model_number,
                    'Brand': brand,
                    'Quantity': quantity,
                    'Notes': notes,
                    'Home Depot Price': prices['Home Depot Price'],
                    'Home Depot Link': prices['Home Depot Link'],
                    'Lowes Price': prices['Lowes Price'],
                    'Lowes Link': prices['Lowes Link']
                }
                
                st.session_state.inventory_data = pd.concat([
                    st.session_state.inventory_data,
                    pd.DataFrame([new_row])
                ], ignore_index=True)
                
                st.success("Item added to inventory!")

# Tab 3: View Inventory
with tab3:
    st.header("Current Inventory")
    
    # Download button for inventory
    if not st.session_state.inventory_data.empty:
        # Create Excel file in memory
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
        st.info("No items in inventory yet. Add items using either the Scanner or Manual Entry tab.")
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
            model_filter = st.text_input("Search by Model Number")
        
        # Apply filters
        filtered_df = st.session_state.inventory_data.copy()
        if brand_filter:
            filtered_df = filtered_df[filtered_df['Brand'].isin(brand_filter)]
        if model_filter:
            filtered_df = filtered_df[filtered_df['Model Number'].str.contains(model_filter, case=False, na=False)]
        
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
