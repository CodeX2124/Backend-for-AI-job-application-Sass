client = AzureOpenAI(
    api_key = os.getenv('AZURE_OPENAI_KEY'),
    api_version="2024-07-01-preview",
    azure_endpoint="https://cognibly-jobs-ai-service.openai.azure.com/openai/deployments/cognibly-gpt4o-mini/chat/completions?api-version=2023-03-15-preview"
)

deployment_name="cognibly-gpt4o-mini"

def generate_job_keywords(role, industry):
    system_prompt = f"""
    You are a helpful assistant that generates an array of strings containing job search keywords based on job preferences. 
    The user will provide the Industry, and Preferred Role & Responsibility.
    Output the keywords as an array of strings. Do not print anything else besides the array.
    """
    prompt = f"""
    Industry: {job_preferences['preferred_industries']}
    Role & Responsibility: {job_preferences['preferred_roles_responsibilities']}
    """
    
    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.40,
            max_tokens=300
        )

        # Get the raw content from the response
        raw_content = response.choices[0].message.content.strip()
        
        # Clean and parse the content
        try:
            # Remove any leading/trailing brackets and whitespace
            cleaned_content = raw_content.strip('[]')
            
            # Split the content into individual items
            items = cleaned_content.split(',')
            
            # Clean each keyword
            keywords_list = []
            for item in items:
                # Remove quotes, newlines, and extra whitespace
                cleaned_item = item.strip().strip('"\'').strip()
                if cleaned_item:  # Only add non-empty items
                    keywords_list.append(cleaned_item)
            
            # Remove any duplicates while preserving order
            keywords_list = list(dict.fromkeys(keywords_list))
            
            # Limit to maximum_keywords
            keywords_list = keywords_list[:maximum_keywords]
            
            print("Cleaned Keywords:", keywords_list)
            return keywords_list

        except Exception as parsing_error:
            print(f"Error parsing keywords: {str(parsing_error)}")
            # If parsing fails, try a simpler approach
            simple_keywords = [k.strip().strip('"\'').strip() for k in raw_content.split(',')]
            simple_keywords = [k for k in simple_keywords if k][:maximum_keywords]
            return simple_keywords

    except Exception as e:
        print(f"Error generating keywords: {str(e)}")
        return []

# Example usage:
if __name__ == "__main__":


