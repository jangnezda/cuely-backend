from trello import TrelloClient, Board

client = TrelloClient(
    api_key='78b036c6db00a520689da78bb58616d0',
    api_secret='7b66542c38cf332c6e8ae8d61fa1d8c80f54707065246c382c7e10face645002',
    token='896e42681adf3f79709a591f3116a626575e73641221501a0a1e41c9fba9ec67',
    token_secret='16809398f9366f2aa0c45efa8795ab18'
)

def process_trello_boards_and_cards(client):
	boards = []
	cards = []

	organizations = client.list_organizations()

	for board in client.list_boards():
		if board.closed is False:

			#TO-DO: compare board last_activity with DB
			board_last_updated = board.date_last_activity.isoformat()

			board_owner = build_board_owner(board)
			board_lists = build_board_lists(board)

			#build everything needed for boards items
			boards.append({
				'trello_board_name' : board.name,
				'trello_board_last_updated' : board_last_updated,
				'trello_board_organization' : get_org_name(organizations, board.organization_id),
				'trello_board_owner' : board_owner,
				'trello_board_other_members' : build_board_members(board, board_owner['name']),
				'trello_board_lists' : parse_lists(board_lists)
			})

			#build everything needed for cards items
			for list in board_lists:
				for card in list['cards']:
					#TO-DO: compare each card last_activity with DB
					card_last_updated = card.dateLastActivity

					cards.append({
						'name' : card.name,
						'last_updated' : card_last_updated.isoformat(),
						'url' : card.url,
						'description' : card.description,
						'checklists' : build_card_checklists(card)
					})

	return {'trello_boards' : boards, 'trello_cards' : cards}

def build_board_members(board, owner_name):
	members = []

	for member in board.all_members():
		if member.full_name != owner_name:
			members.append({
				'name' : member.full_name,
				'avatar' : '' if (member.avatar_hash == None) else ('https://trello-avatars.s3.amazonaws.com/' + member.avatar_hash + '/original.png')
			})

	return members

def build_board_owner(board):
	admins = board.admin_members()
	admin = {
		'name' : admins[0].full_name,
		'avatar' : '' if (admins[0].avatar_hash == None) else ('https://trello-avatars.s3.amazonaws.com/' + admins[0].avatar_hash + '/original.png')
	}

	return admin

def get_org_name(organizations, organization_id):
	for organization in organizations:
		if organization_id == organization.id:
			return organization.name

	return None

def build_board_lists(board):
	lists = []
	
	for list in board.all_lists():
		if list.closed == False:
			lists.append({
				'name' : list.name,
				'cards' : build_list_cards(list)
			})

	return lists

def build_card_checklists(card):
	checklists = []

	org_checklists = card.checklists
	org_checklists = card.checklists

	if org_checklists != None:
		for checklist in org_checklists:
			items = []

			if checklist.items != None:
				for item in checklist.items:
					items.append({
						'name' : item['name'],
						'checked' : item['checked']
					})

			checklists.append({
				'name' : checklist.name,
				'items': items
			})

	return checklists

def build_list_cards(list):
	cards = []

	for card in list.list_cards():
		if card.closed == False:
			cards.append(card)

	return cards

def parse_lists(org_lists):
	lists = []

	for list in org_lists:
		cards = []

		for card in list['cards']:
			cards.append({
				'name' : card.name,
				'url' : card.url,
				'last_changed' : card.dateLastActivity
			})

		lists.append({
			'name' : list['name'],
			'cards' : cards
			})

	return lists

process_trello_boards(client)

