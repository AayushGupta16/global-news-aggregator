'''
Feed the to string of the article content to generate a summary, takeaway, and relevance of the article.

First step is to translate the article into English.
Then use Gemini to explain what the article is about and its broader relevance.
Score it using the likert scale, if it is a high enough score continue with next steps.
- Make a 2 sentence headline of the article (kinda like a catching news headline)
- Have a 2 paragraph summary & takeaway of the article
- Tag it with relevant categories 
- return article headline, summary/takeaway, and categories as a custom object
'''