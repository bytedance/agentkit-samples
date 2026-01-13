# Data Analysis with Datalake Project

## Overview

This is a data analysis framework built on LanceDB, using the IMDB dataset. It supports various functions including structured data querying, unstructured hybrid retrieval, metadata search, and unstructured data processing.

## Technology Stack

- **LanceDB**: Used for efficient metadata search, vector and structured data storage, and retrieval.
- **DuckDB**: Used for SQL queries on structured data.

## Core Functions

### Structured Data Query (`duckdb_sql_execution.py`)

- **Functionality**: Allows users to query structured data using SQL statements.
- **Technology**: Based on the DuckDB database engine.
- **Use Case**: Performing traditional structured data queries, filtering, and aggregation operations.

### Unstructured Hybrid Retrieval (`lancedb_hybrid_execution.py`)

- **Functionality**: Supports combining structured queries with vector retrieval to achieve hybrid queries.
- **Technology**: Based on LanceDB's vector retrieval capabilities.
- **Use Case**: Handling query requirements that involve both structured attributes and unstructured content.

### Metadata Search (`catalog_discovery.py`)

- **Functionality**: Provides search and discovery features for dataset metadata.
- **Technology**: Based on metadata management with a catalog structure.
- **Use Case**: Helping users understand the structure and content of available datasets.

### Unstructured Data Processing (`video_generation.py`)

- **Functionality**: Supports converting unstructured data (like images) into videos.
- **Technology**: Based on video generation algorithms.
- **Use Case**: Implementing image-to-video conversion.

## Agent Capabilities

- Tool Calling
- Large Language Models

## Directory Structure

```bash
05_data_analysis_with_datalake/
├── agent.py
├── prompts.py
├── requirements.txt
├── settings.txt
└── tools/
    ├── catalog_discovery.py
    ├── duckdb_sql_execution.py
    ├── lancedb_hybrid_execution.py
    └── video_generation.py
├── client.py
└── web/
    └── app.py
```

## Dataset Description

This project uses the IMDB dataset, which consists of two main components:

### 1. Metadata Table

Provides an overall description and structural information of the dataset, helping users understand the available data resources. It includes descriptions, data types, sample values, and possible value ranges for each column.

### 2. IMDB Top 1000 Movies Table (`imdb_top_1000`)

Contains detailed information for 1000 movies, with the following main fields:

| Field Name              | Type   | Description                                                              |
| ----------------------- | ------ | ------------------------------------------------------------------------ |
| `series_title`          | String | Movie title                                                              |
| `released_year`         | String | Release year (Note: Although it's a number, it is a string type, so comparisons need to be enclosed in single quotes) |
| `director`              | String | Director                                                                 |
| `genre`                 | String | Movie genre                                                              |
| `imdb_rating`           | Float  | IMDB rating                                                              |
| `poster_curde_link`     | String | Link to the movie's thumbnail poster                                     |
| `poster_precision_link` | String | Link to the movie's high-definition poster                               |

## Local Execution

### Method 1: Using the Python Client

When running with AgentKit, you can connect using the client.

```bash
python client.py
```

### Method 2: Using the Web Interface

```bash
streamlit run web/app.py
```

## AgentKit Deployment

### Configuration File Settings

Edit the `05_data_analysis_with_datalake/settings.txt` file and optionally configure the following, or export these environment variables instead.

```text
MODEL_AGENT_API_KEY=your_api_key_here
VOLCENGINE_ACCESS_KEY=your_ak
VOLCENGINE_SECRET_KEY=your_sk
```

### Deploying via Command Line

```bash
uv python install 3.12
uv venv -p 3.12 .venv
source .venv/bin/activate
uv pip install -r requirements.txt

# CLI Run
adk run 05_data_analysis_with_datalake
# Prompt: what is data and list movies with score > 9 from director Francis Ford

# veadk Run
veadk web

# Run on AgentKit
agentkit config --tos_bucket <your bucket name>
agentkit launch
```

## Example Prompts

1.  **Q1: What data do you have?**
2.  **Q2: Give me some sample data.**
3.  **Q3: Which movies directed by Ang Lee have a rating over 7?**
4.  **Q4: Among the movies directed by Ang Lee with a rating over 7, which one has an animal in its poster?**
5.  **Q5: Turn the movie poster for "Life of Pi" into a video.**
6.  **Q6: For movies by Hayao Miyazaki with a rating over 7.5 and a poster containing an airplane, generate a video.**
7.  **Q7: Database Overview - List all table names in the current database and describe the main purpose of each table.**
8.  **Q8: Schema Validation - Query the detailed schema information for the `imdb_top_1000` table to confirm the specific data type of the `released_year` field.**
9.  **Q9: Data Sampling - Randomly select and display 5 complete records from the `imdb_top_1000` table.**
10. **Q10: Total Count - Count the total number of movie records in the dataset.**
11. **Q11: Equality Filter - Query for a list of all movies where the Director is "Christopher Nolan".**
12. **Q12: Numerical Range - Filter for movies with an IMDB rating strictly greater than 9.0.**
13. **Q13: Implicit Type Conversion - Retrieve all movies released in or after the year 2000.**
14. **Q14: Multiple Condition Combination - Query for movies with "Sci-Fi" in their Genre and a rating higher than 8.5.**
15. **Q15: Sorted Retrieval - Return the titles of the top 10 movies, sorted by rating in descending order.**
16. **Q16: Aggregation Calculation - Calculate the average rating of all movies directed by "Steven Spielberg".**
17. **Q17: Visual Feature Retrieval - Retrieve movies whose posters contain the visual element of a "Car".**
18. **Q18: Specific Object Recognition - Find movies whose posters feature a "Gun" or "Weapon".**
19. **Q19: Mixed Condition Filtering - Filter for movies with a rating over 8.0 and whose posters contain an "Animal".**
20. **Q20: Semantic Fuzzy Matching - Recommend movies about "Space Exploration" or "interstellar travel" based on semantic retrieval.**
21. **Q21: Specified Object Generation - Call the video generation tool to convert the poster of the movie "The Godfather" into a video.**
22. **Q22: Conditional Trigger Generation - Identify the highest-rated movie in the dataset and generate a video based on its poster.**
23. **Q23: Specific Entity Generation - Query for the highest-rated work by director "Hayao Miyazaki" and perform video generation on its poster.**
24. **Q24: Comparative Analysis - Count and compare the number of movies directed by "Christopher Nolan" and "Quentin Tarantino" with a rating greater than 8.5.**
25. **Q25: Fuzzy Time Range - List the top 3 action movies released between 1990 and 1999 with the highest ratings.**
26. **Q26: End-to-End Comprehensive Test - Retrieve the highest-rated movie released after 2010 whose poster contains a "portrait", and generate a video from its poster.**

## Execution Flow

When a user asks a question, the system will follow this process:

1.  **Discovery Phase**: Calls the `catalog_discovery` tool to confirm available table names and field information.
2.  **Data Analysis Phase (Query)**:
    -   For structured statistical or filtering queries, calls the `duckdb_sql_execution` tool to execute SQL queries.
    -   For semantic, visual, or hybrid retrieval queries, calls the `lancedb_hybrid_execution` tool to perform vector retrieval.
    -   For unstructured data processing like image-to-video, calls the `video_generation` tool to perform the corresponding action.
3.  **Result Handling Phase**:
    -   If the result is empty `[]`, it directly answers the user "Not found."
    -   If the result is normal, it immediately returns the final answer.

## Demonstration

Datalake demonstration.

## FAQ

None.

## Code License

This project is licensed under the Apache 2.0 License.
