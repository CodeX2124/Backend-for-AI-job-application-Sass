import re, os
from collections import Counter
from openai import AzureOpenAI # type: ignore
import json
from dotenv import load_dotenv # type: ignore
from urllib.parse import urlencode, quote_plus
#from .extensions import logger

load_dotenv()

client = AzureOpenAI(
    api_key = os.getenv('AZURE_OPENAI_KEY'),
    api_version="2024-07-01-preview",
    azure_endpoint="https://cognibly-jobs-ai-service.openai.azure.com/openai/deployments/cognibly-gpt4o-mini/chat/completions?api-version=2023-03-15-preview"
)

deployment_name="cognibly-gpt4o-mini"


#See the below examples for query formation conventions:
#Glassdoor:
#https://www.glassdoor.com/Job/texas-us-pre-sales-engineer-jobs?sortBy=date_desc
#optional params:
#remoteWorkType=1 (remote job)
#maxSalary=170000&minSalary=121000 (salary requirements)
#minRating=4.0 (company prestige)
#fromAge=14 (14 days since job was posted)

#glassdoor_search_link=(f"https://www.glassdoor.com/Job/{location_keyword}-{keywords}?sortBy=date_desc")

#Indeed:
#https://www.indeed.com/jobs?q=pre+sales+engineer&l=Houston
#optional params:
#radius=50 (search radius from location <=50mi)
#sc=0kf:attr(DSQF7); (remote jobs)
#sc=0kf:attr(PAXZC); (hybrid jobs, does not include remote)
#salary included as a string concatenated to keyword like "software engineer $120,000"

#indeed_search_link=(f"https://www.indeed.com/jobs?q={keywords}&l={location_keyword}")

#SimplyHired:
#https://www.simplyhired.com/search?q=pre+sales+engineer&l=Texas&s=d
#optional params:
#remoteWorkType=1 (remote job)
#mip=115000 (minimum pay = $115,000 USD)
#sr=50 (search radius from location <=50mi)
#t=14 (14 days since job was posted)
#simplyhired_search_link=(f"https://www.simplyhired.com/search?q={keywords}&l={location_keyword}&s=d")

def generate_job_keywords(job_preferences, maximum_keywords=10):
    system_prompt = f"""
    You are a helpful assistant that generates an array of {str(maximum_keywords)} strings containing job search keywords based on job preferences. 
    The user will provide the Ideal Work Situation, Preferred Industries, and Preferred Roles & Responsibilities.
    Output the keywords as an array of strings. Do not print anything else besides the array.
    """
    prompt = f"""
    Preferred Industries: {job_preferences['preferred_industries']}
    Preferred Roles & Responsibilities: {job_preferences['preferred_roles_responsibilities']}
    """
    
    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.40,
            max_tokens=(maximum_keywords*5)
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
    job_preferences = {
        'ideal_work_situation': 'Fast-paced startup environment with opportunities for growth',
        'preferred_industries': ['Technology', 'Finance'],
        'preferred_roles_responsibilities': ['Data analysis', 'Machine learning', 'Project management'],
        'willing_to_relocate': 'yes',
        'relocation_preference': 'specific',
        'preferred_locations': ["Dallas, TX", "Austin, TX"],
        'remote_work_type': 'remote',  # Options: 'remote', 'hybrid', 'onsite'
        'min_salary': 100000,
        'max_salary': 150000,
        'min_rating': 4.0,
        'from_age': 14  # Days since job was posted
    }

    #not interested in testing generate_job_keywords as this is already confirmed to be working.
    #keywords = generate_job_keywords(job_preferences)
    #print("Generated Keywords:", keywords)
    keywords = [
    "PMP Certified",
    "Business Technology",
    "Education Technology",
    "Cloud Solutions",
    "Program Management",
    "Software Development",
    "Cloud Architecture",
    "Higher Education Leadership",
    "IT Project Management",
    "Chief Technology Officer",
    "Technical Expertise",
    "Cloud Computing Specialist",
    "Educational Program Development",
    "Technology Integration",
    "Strategic Technology Planning"
    ]
    urls = generate_urls(
        keywords,
        preferred_locations=job_preferences['preferred_locations'],
        remote_work_type=job_preferences.get('remote_work_type'),
        min_salary=job_preferences.get('min_salary'),
        max_salary=job_preferences.get('max_salary'),
        min_rating=job_preferences.get('min_rating'),
        from_age=job_preferences.get('from_age')
    )
    print("\nSample output for testing only. This script not intended for standalone usage.")
    print("\nGenerated URLs:")
    for url in urls:
        print(url)
