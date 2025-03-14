import streamlit as st
import pandas as pd
from datetime import datetime
import asyncio
from product_search import ProductSearcher
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize session state for inventory data
if 'inventory_data' not in st.session_state:
    st.session_state.inventory_data = pd.DataFrame(columns=[
        'Date Added', 'Product Number', 'Brand', 'Model Name', 'Category',
        'Quantity', 'MSRP', 'Notes'
    ])

def main():
    st.title("Toilet Box Scanner Inventory Management")
    
    # Initialize ProductSearcher
    searcher = ProductSearcher()
    
    # Create form for product entry
    with st.form("product_entry_form"):
        product_number = st.text_input("Product Number")
        brand_options = ["Kohler", "Toto", "American Standard", "Delta", "Moen", "Other"]
        brand = st.selectbox("Brand", brand_options)
        model_name = st.text_input("Model Name")
        category = st.text_input("Category")
        quantity = st.number_input("Quantity", min_value=1, value=1)
        msrp = st.number_input("MSRP", min_value=0.0, value=0.0)
        notes = st.text_area("Notes")
        
        submit_button = st.form_submit_button("Add Product")
        
        if submit_button:
            try:
                # Validate product number
                if not product_number:
                    st.error("Please enter a product number.")
                    return
                
                # Add product with error handling
                with st.spinner('Searching retailers for pricing...'):
                    try:
                        search_results = asyncio.run(searcher.search_all_retailers(
                            product_number=product_number,
                            brand=brand if brand != "Other" else None
                        ))
                        
                        if search_results.error:
                            st.warning(f"Some searches failed: {search_results.error}")
                        
                        # Update form with found information
                        if search_results.brand and brand == "Other":
                            brand = search_results.brand
                        if not model_name and search_results.product_name:
                            model_name = search_results.product_name
                        if not category and search_results.category:
                            category = search_results.category

                        # Create new row with enhanced information
                        new_row = {
                            'Date Added': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            'Product Number': product_number,
                            'Brand': brand,
                            'Model Name': model_name,
                            'Category': category,
                            'Quantity': quantity,
                            'MSRP': msrp,
                            'Notes': notes
                        }

                        # Add retailer information
                        for retailer, price_info in search_results.retailers.items():
                            new_row[f'{retailer.title()} Price'] = price_info.raw_price
                            new_row[f'{retailer.title()} Link'] = price_info.url
                            new_row[f'{retailer.title()} In Stock'] = 'Yes' if price_info.in_stock else 'No'

                        # Add to inventory
                        st.session_state.inventory_data = pd.concat([
                            st.session_state.inventory_data,
                            pd.DataFrame([new_row])
                        ], ignore_index=True)

                        # Show success message with details
                        st.success("Product added to inventory!")
                        
                        # Show retailer links
                        st.subheader("Retailer Links")
                        for retailer, price_info in search_results.retailers.items():
                            if price_info.url:
                                st.markdown(f"[View on {retailer.title()}]({price_info.url})")

                        # Show specifications if available
                        if search_results.specifications:
                            with st.expander("Product Specifications"):
                                for key, value in search_results.specifications.items():
                                    st.text(f"{key}: {value}")

                    except Exception as e:
                        st.error(f"Error adding product: {str(e)}")
                        logger.error(f"Error adding product {product_number}: {str(e)}", exc_info=True)

            except Exception as e:
                st.error(f"Error processing form: {str(e)}")
                logger.error(f"Error processing form: {str(e)}", exc_info=True)

    # Display inventory table
    if not st.session_state.inventory_data.empty:
        st.subheader("Current Inventory")
        st.dataframe(st.session_state.inventory_data)

if __name__ == "__main__":
    main()
