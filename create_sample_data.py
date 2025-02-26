import pandas as pd
import numpy as np

# Create sample data
data = {
    "Source Doc": [
        "Explain the concept of quantum entanglement in simple terms.",
        "What are the main differences between Python and JavaScript?",
        "How does photosynthesis work in plants?",
        "Explain the theory of relativity in simple terms.",
        "What is the significance of the Fibonacci sequence in nature?",
        # Add more complex questions that would benefit from reasoning
        "Compare and contrast different approaches to implementing authentication in web applications.",
        "Explain how neural networks learn patterns in data.",
        "What are the implications of Moore's Law on future computing?",
        "How do cryptocurrencies maintain security and prevent double-spending?",
        "Explain the concept of technical debt in software development."
    ] * 500  # Multiply to get 5000 rows
}

# Create DataFrame
df = pd.DataFrame(data)

# Save to Excel
df.to_excel("sample_data.xlsx", index=False)

print(f"Created sample_data.xlsx with {len(df)} rows") 