import streamlit as st
import pandas as pd
from datetime import datetime
import io

# Set page config
st.set_page_config(
    page_title="Toilet Inventory & Pricing Scanner",
    page_icon="🚽",
    layout="wide"
)

# Initialize session state for inventory
if 'inventory_data' not in st.session_state:
    st.session_state.inventory_data = pd.DataFrame(
        columns=[
            'Date Added',
            'Product Number',
            'Brand',
            'Model Name',
            'Category',
            'Quantity',
            'MSRP',
            'Notes',
            'Ferguson Price',
            'Ferguson Link',
            'Home Depot Price',
            'Home Depot Link',
            'Lowes Price',
            'Lowes Link'
        ]
    )

# Main app header
st.title("🚽 Toilet Inventory & Pricing Scanner")

# Create tabs
tab1, tab2, tab3 = st.tabs(["Add Product", "View Inventory", "Analytics"])

# Tab 1: Add Product
with tab1:
    st.header("Add New Product")
    
    # Input method selection
    input_method = st.radio(
        "Choose Input Method:",
        ["Manual Entry", "Barcode Scanner (Coming Soon)"]
    )
    
    if input_method == "Manual Entry":
        with st.form("product_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                product_number = st.text_input("Product Number")
                brand = st.selectbox("Brand", ["Kohler", "TOTO", "American Standard", "Other"])
                model_name = st.text_input("Model Name")
                
            with col2:
                category = st.selectbox(
                    "Category",
                    ["One-Piece Toilet", "Two-Piece Toilet", "Tank", "Bowl", "Other"]
                )
                quantity = st.number_input("Quantity", min_value=1, value=1)
                msrp = st.number_input("MSRP ($)", min_value=0.0, value=0.0)
            
            notes = st.text_area("Notes")
            
            submit_button = st.form_submit_button("Add to Inventory")
            
            if submit_button:
                # Add to inventory
                new_row = {
                    'Date Added': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'Product Number': product_number,
                    'Brand': brand,
                    'Model Name': model_name,
                    'Category': category,
                    'Quantity': quantity,
                    'MSRP': msrp,
                    'Notes': notes,
                    'Ferguson Price': 'N/A',
                    'Ferguson Link': '',
                    'Home Depot Price': 'N/A',
                    'Home Depot Link': '',
                    'Lowes Price': 'N/A',
                    'Lowes Link': ''
                }
                
                st.session_state.inventory_data = pd.concat([
                    st.session_state.inventory_data,
                    pd.DataFrame([new_row])
                ], ignore_index=True)
                
                st.success("Product added to inventory!")

# Tab 2: View Inventory
with tab2:
    st.header("Current Inventory")
    
    if not st.session_state.inventory_data.empty:
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            brand_filter = st.multiselect(
                "Filter by Brand",
                options=st.session_state.inventory_data['Brand'].unique()
            )
        with col2:
            category_filter = st.multiselect(
                "Filter by Category",
                options=st.session_state.inventory_data['Category'].unique()
            )
        with col3:
            search_term = st.text_input("Search by Product Number or Model")
        
        # Apply filters
        filtered_df = st.session_state.inventory_data.copy()
        if brand_filter:
            filtered_df = filtered_df[filtered_df['Brand'].isin(brand_filter)]
        if category_filter:
            filtered_df = filtered_df[filtered_df['Category'].isin(category_filter)]
        if search_term:
            mask = (
                filtered_df['Product Number'].str.contains(search_term, case=False, na=False) |
                filtered_df['Model Name'].str.contains(search_term, case=False, na=False)
            )
            filtered_df = filtered_df[mask]
        
        # Display inventory
        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True
        )
        
        # Download button
        excel_buffer = io.BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            filtered_df.to_excel(writer, index=False)
        
        st.download_button(
            label="Download Inventory as Excel",
            data=excel_buffer.getvalue(),
            file_name=f"toilet_inventory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # Summary statistics
        st.subheader("Inventory Summary")
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Products", len(filtered_df))
        with col2:
            st.metric("Total Items", filtered_df['Quantity'].sum())
        with col3:
            st.metric("Total Value (MSRP)", f"${filtered_df['MSRP'].sum():,.2f}")
        with col4:
            st.metric("Number of Brands", len(filtered_df['Brand'].unique()))

# Tab 3: Analytics
with tab3:
    st.header("Inventory Analytics")
    
    if not st.session_state.inventory_data.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Products by Brand")
            brand_counts = st.session_state.inventory_data['Brand'].value_counts()
            st.bar_chart(brand_counts)
        
        with col2:
            st.subheader("Products by Category")
            category_counts = st.session_state.inventory_data['Category'].value_counts()
            st.bar_chart(category_counts)
    else:
        st.info("Add some products to see analytics!")
