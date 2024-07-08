import pandas as pd

# Load the existing sales data
file_path = 'Generated_Sales_Data.csv'  # replace with the path to your file
sales_df = pd.read_csv(file_path)

# Convert the sales values to integers
sales_df['sales'] = sales_df['sales'].astype(int)

# Save the updated dataframe to a new CSV file
updated_file_path = 'sales_data.csv'  # replace with the desired path to save the updated file
sales_df.to_csv(updated_file_path, index=False)

print(f"Updated file saved to {updated_file_path}")
