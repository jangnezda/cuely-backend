FREE = 'Free'
STARTUP = 'Startup'
PRO = 'Pro'

PLANS = {
    FREE: {
        'users': 3,
        'objects': 5000,
        'user_integrations': False
    },
    STARTUP: {
        'users': 10,
        'objects': 50000,
        'user_integrations': True
    },
    PRO: {
        'users': 50,
        'objects': 500000,
        'user_integrations': True
    },
}
