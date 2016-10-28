from pypedriver import Client
import json

def process_all_pipedrive_deals(api_key):
	"""Outputs all Deal objects prepared for Cuely in an array

    """
	pipedrive = Client(api_key)	
	deals = pipedrive.Deal.fetch_all()	
	stages = process_pipedrive_stages(pipedrive)
	users = process_pipedrive_users(pipedrive)

	deals_output = []

	for deal in deals:
	    deals_output.append(process_single_deal(pipedrive, deal, stages, users))

	json_output = json.dumps(deals_output)
	return json_output

def process_single_deal(pipedrive, deal, stages, users):
	"""Prepares Cuely ready Deal object

    """
	tempDeal = {}
	tempDeal['pipedrive_deal_title'] = deal.title
	tempDeal['pipedrive_deal_value'] = deal.value or None
	tempDeal['pipedrive_deal_currency'] = deal.currency if tempDeal['pipedrive_deal_value'] else None
	tempDeal['pipedrive_deal_org_name'] = deal.org_id['name']
	tempDeal['pipedrive_deal_last_updated'] = deal.update_time
	tempDeal['pipedrive_deal_stage'] = stages[(deal.stage_id-1)]
	tempDeal['pipedrive_deal_status'] = deal.status
	tempDeal['pipedrive_deal_url'] = 'https://' + deal.org_id['cc_email'].split('@')[0] + '.pipedrive.com/deal/' + str(deal.id)
	tempDeal['pipedrive_deal_contacts'] = process_pipedrive_deal_contacts(pipedrive, deal)
	tempDeal['pipedrive_deal_users'] = process_pipedrive_deal_users(pipedrive, deal, users)
	tempDeal['pipedrive_deal_activities'] = process_pipedrive_deal_activities(pipedrive, deal, users)

	return tempDeal

def process_pipedrive_deal_contacts(pipedrive, deal):
	"""Get all Contacts associated with particular Deal

    """
	contactsArray = []
	tempContact = {}
	tempContact['name'] = deal.person_id['name']
	tempContact['email'] = deal.person_id['email'][0]['value'] or None
	contactsArray.append(tempContact)

	if (deal.participants_count > 1):
		contacts = pipedrive.Participant.fetch_all(filter_id=deal.id)

		for contact in contacts:
			if (contact.person['name'] != deal.person_id['name']):
				tempContact = {}
				tempContact['name'] = contact.person['name']
				tempContact['email'] = contact.person['email'][0]['value'] or None
				contactsArray.append(tempContact)

	return contactsArray

def process_pipedrive_deal_activities(pipedrive, deal, users_list):
	"""Get all Activities associated with particular Deal

    """
	activitiesArray = []

	if (deal.done_activities_count > 1):
		activities = pipedrive.ActivityDeal.fetch_all(filter_id=deal.id)

		for activity in activities:
			if(activity.done):
				tempActivity = {}
				tempActivity['pipedrive_deal_activity_subject'] = activity.subject
				tempActivity['pipedrive_deal_activity_type'] = activity.type
				tempActivity['pipedrive_deal_activity_user_name'] = get_user_by_id(activity.assigned_to_user_id, users_list)['pipedrive_user_name']
				tempActivity['pipedrive_deal_activity_done_time'] = activity.marked_as_done_time
				tempActivity['pipedrive_deal_activity_contact'] = activity.person_name
				activitiesArray.append(tempActivity)

	return activitiesArray

def process_pipedrive_deal_users(pipedrive, deal, users_list):
	"""Get all Users associated with particular Deal

    """
	usersArray = []
	tempUser = {}

	userDetails = get_user_by_id(deal.user_id['id'], users_list)
	tempUser['pipedrive_deal_user_name'] = userDetails['pipedrive_user_name']
	tempUser['pipedrive_deal_user_email'] = userDetails['pipedrive_user_email'] or None
	tempUser['pipedrive_deal_user_icon_url'] = userDetails['pipedrive_user_icon_url']
	usersArray.append(tempUser)

	if (deal.followers_count > 1):
		users = pipedrive.FollowerDeal.fetch_all(filter_id=deal.id)

		for user in users:
			if (deal.user_id['id'] != user.user_id):
				tempUser = {}
				userDetails = get_user_by_id(user.user_id, users_list)
				tempUser['pipedrive_deal_user_name'] = userDetails['pipedrive_user_name']
				tempUser['pipedrive_deal_user_email'] = userDetails['pipedrive_user_email'] or None
				tempUser['pipdrive_deal_user_icon_url'] = userDetails['pipedrive_user_icon_url'] or None
				usersArray.append(tempUser)

	return usersArray

def process_pipedrive_users(pipedrive):
	"""Get an array of all User objects

    """
	users = pipedrive.User.fetch_all()
	userArray = []

	for user in users:
		if user.active_flag:
			tempUser = {}
			tempUser['pipedrive_user_id'] = user.id
			tempUser['pipedrive_user_name'] = user.name
			tempUser['pipedrive_user_email'] = user.email
			tempUser['pipedrive_user_icon_url'] = user.icon_url
			userArray.append(tempUser)

	return userArray

def get_user_by_id(id, users_list):
	"""Get the full User object by user id

    """
	for user in users_list:
		if (user['pipedrive_user_id'] == id):
			return user

def process_pipedrive_stages(pipedrive):
	"""Get an array of all Stage names

    """
	stages = pipedrive.Stage.fetch_all()
	stageArray = []

	for stage in stages:
		stageArray.append(stage.name)

	return stageArray

def get_deals_last_updated(api_key):
	"""Get update timestamp on all Deals

    """
	pipedrive = Client(api_key)	
	deals = pipedrive.Deal.fetch_all()
	deals_updated_output=[]

	for deal in deals:
		tempDeal = {}
		tempDeal['id'] = deal.id
		tempDeal['last_updated'] = deal.update_time
		deals_updated_output.append(tempDeal)

	return deals_updated_output

	#TO-DO diff timestamps with our DB and then check for more info on those deals that make sense



api_key = '83cfabeb9c398a7addad65ee5c4f9a429dfbb94d'

print (process_all_pipedrive_deals(api_key))
#print (get_deals_last_updated(api_key))

