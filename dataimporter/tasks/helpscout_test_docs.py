import helpscout
from dateutil.parser import parse as parse_dt

clientdocs = helpscout.ClientDocs()
client = helpscout.Client()
clientdocs.api_key = "e4c162bb6da94abfdb4a0839d6232638278eba20"
client.api_key = "a0b9486cb9ebd2e1436d15670a692c2e0d5ebd8d"


def get_articles(client, clientdocs):
	articles = []

	for collection in clientdocs.collections():
		for category in clientdocs.categories(collection.id):
			for article in clientdocs.articles(category.id):

				#TO-DO: Compare article last_updated timestamp to the one in the DB - if newer, then pull out the rest
				temp_article_details = clientdocs.article(article.id)

				articles.append({
					'name' : article.name,
					'status' : article.status,
					'last_updated' : article.updatedat,
					'category' : category.name if not category.name == 'Uncategorized' else None,
					'collection' : collection.name,
					'text' : temp_article_details.text,
					'users' : get_users(article, client),
					'keywords' : temp_article_details.keywords,
					'url' : article.publicurl
				});
				
	return articles	

def get_user(id, client):
	user = client.user(id)

	return {
		'name' : user.firstname + ' ' + user.lastname,
		'photourl' : user.photourl
	}

def get_users(article, client):
	users = []
	users.append(get_user(article.createdby, client))

	if article.createdby != article.updatedby:
		users.append(get_user(article.updatedby, client))

	return users

# print(get_articles(client, clientdocs))
