{
    'name': 'Global Hide Datetime',
    'version': '1.0',
    'summary': 'Hide time from all datetime fields globally',
    'category': 'Web',
    'depends': ['web'],
    'assets': {
        'web.assets_backend': [
            'hide_datetime/static/src/js/hide_datetime.js',
        ],
    },
    'installable': True,
    'application': False,
}
