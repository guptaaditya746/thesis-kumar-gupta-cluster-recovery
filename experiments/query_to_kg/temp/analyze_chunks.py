import pandas as pd
import matplotlib.pyplot as plt

# 1. Define the path to your JSONL file
file_path = "backend/app/data/chunks/contextualized_chunks.jsonl"

print(f"Loading data from {file_path}...\n")

# Read the JSONL file into a Pandas DataFrame
# lines=True is required for .jsonl files
df = pd.read_json(file_path, lines=True)

# 2. Basic Dataset Overview
print("=== Dataset Overview ===")
print(f"Total chunks found: {len(df)}")
print(f"Columns: {', '.join(df.columns)}\n")

# 3. Paper & Section Distribution
print("=== Chunks per Paper ===")
print(df['paper_id'].value_counts().head(10)) # Top 10 papers
print("\n=== Top Sections by Chunk Count ===")
print(df['section_title'].value_counts().head(10))

# 4. Text Length Analysis (Word Counts)
print("\n=== Analyzing Text Lengths ===")
# Calculate word counts by splitting on whitespace
df['raw_text_word_count'] = df['raw_text'].apply(lambda x: len(str(x).split()))
df['summary_word_count'] = df['contextual_summary'].apply(lambda x: len(str(x).split()) if pd.notnull(x) else 0)
df['index_text_word_count'] = df['index_text'].apply(lambda x: len(str(x).split()) if pd.notnull(x) else 0)

# Display statistical summary of the word counts
print(df[['raw_text_word_count', 'summary_word_count', 'index_text_word_count']].describe().round(2))

# 5. Missing Data Check
print("\n=== Missing Values Check ===")
missing_data = df.isnull().sum()
missing_data = missing_data[missing_data > 0]
if not missing_data.empty:
    print(missing_data)
else:
    print("No missing values found in any columns.")

# Optional: Uncomment below to plot and save a histogram of text lengths
# df[['raw_text_word_count', 'summary_word_count']].plot(kind='hist', bins=50, alpha=0.5, title="Word Count Distribution")
# plt.xlabel("Number of Words")
# plt.savefig("text_lengths_histogram.png")
# print("\nSaved text lengths histogram to 'text_lengths_histogram.png'")
