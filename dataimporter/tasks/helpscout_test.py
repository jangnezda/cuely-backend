import helpscout
from dateutil.parser import parse as parse_dt

client = helpscout.Client()
client.api_key = "a0b9486cb9ebd2e1436d15670a692c2e0d5ebd8d"

mailboxes = {m.id: m.name for m in client.mailboxes()}

def get_all_conversations(client, mailboxes):
	for m in mailboxes:
		folders = {f.id: f.name for f in client.folders(m)}
		conversations = []

		for conversation in client.conversations_for_mailbox(m):
			conversations.append({
				'id' : conversation.id,
				'mailbox' : mailboxes.get(m),
				'folder' : folders.get(conversation.folderid),
				'status' : conversation.status,
				'owner' : conversation.owner,
				'subject' : conversation.subject,
				'last_updated' : conversation.usermodifiedat,
				'tags' : conversation.tags,
				'customer' : get_customer(conversation.customer)
			})

		return conversations

def get_all_customers(client):
	customers = []

	for customer in client.customers():
		customers.append({
			'id' : customer.id,
			'name' : customer.firstname + ' ' + customer.lastname,
			'organization' : customer.organization,
			'last_updated' : customer.modifiedat
		})
		
	return customers

def get_complete_customers(client, mailboxes):
	temp_conversations = get_all_conversations(client, mailboxes)
	customers = []

	for customer in get_all_customers(client):
		conversations = []
		temp_customer_emails = []
		temp_customer_last_updated = 0
		temp_customer_mailbox = ''
		temp_customer_folder = ''
		temp_customer_status = ''

		for conversation in temp_conversations:
			if conversation['customer']['id'] == customer['id']:

				#TO-DO: Compare conversation last_updated timestamp to the one in the DB - if newer, then pull out also conversation threads
				conversation['threads'] = get_conversation_threads(conversation['id'])

				conversations.append(conversation)

				if conversation['customer']['email'] not in temp_customer_emails:
					temp_customer_emails.append(conversation['customer']['email'])

				if (temp_customer_last_updated == 0) or (parse_dt(temp_customer_last_updated).timestamp() < parse_dt(conversation['last_updated']).timestamp()):
					temp_customer_last_updated = conversation['last_updated']
					temp_customer_mailbox = conversation['mailbox']
					temp_customer_folder = conversation['folder']
					temp_customer_status = conversation['status']

		customer['last_mailbox'] = temp_customer_mailbox
		customer['last_folder'] = temp_customer_folder
		customer['last_status'] = temp_customer_status
		customer['last_updated'] = temp_customer_last_updated
		customer['emails'] = temp_customer_emails
		customer['conversations'] = conversations

		customers.append(customer)

	return customers

def get_customer(customer):
	customer_obj = {
		'id' : customer['id'],
		'name' : customer['firstName'] + ' ' + customer['lastName'],
		'email' : customer['email']
	}
	return customer_obj

def get_conversation_threads(conversation_id):
	threads = []

	for thread in client.conversation(conversation_id).threads:	
		threads.append({
			'created' : thread['createdAt'],
			'created_by_id' : thread['createdBy']['id'],
			'created_by_name' : thread['createdBy']['firstName'] + ' ' + thread['createdBy']['lastName'],
			'body' : thread['body']
		})

	return threads


# print(get_complete_customers(client, mailboxes))

