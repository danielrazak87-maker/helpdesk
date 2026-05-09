"""
Pre-defined ticket category templates for structured issue reporting.
"""

TICKET_TEMPLATES = {
    'network': {
        'name': 'Network Issue',
        'icon': '🌐',
        'description_guide': [
            'Location/Room:',
            'Type of issue (no internet, slow, outage):',
            'Affected devices (WiFi/cabled):',
            'When did it start?:',
        ],
        'fields': [
            {'name': 'location', 'label': 'Location/Room', 'type': 'text', 'required': True},
            {'name': 'issue_type', 'label': 'Issue Type', 'type': 'select',
             'options': ['No Internet', 'Slow Connection', 'Complete Outage', 'WiFi Issue', 'Other'],
             'required': True},
        ],
        'default_priority': 'high',
        'default_category': 'network',
    },
    'hardware': {
        'name': 'Hardware Issue',
        'icon': '💻',
        'description_guide': [
            'Device type and model:',
            'Asset tag / serial number:',
            'Description of issue:',
            'Urgency:',
        ],
        'fields': [
            {'name': 'device_type', 'label': 'Device Type', 'type': 'select',
             'options': ['Laptop', 'Desktop', 'Monitor', 'Printer', 'Phone', 'Tablet', 'Other'],
             'required': True},
        ],
        'default_priority': 'medium',
        'default_category': 'hardware',
    },
    'software': {
        'name': 'Software Issue',
        'icon': '🖥️',
        'description_guide': [
            'Software name and version:',
            'What were you trying to do?:',
            'What actually happened?:',
            'Error message (if any):',
        ],
        'fields': [
            {'name': 'software_name', 'label': 'Software Name', 'type': 'text', 'required': True},
            {'name': 'error_message', 'label': 'Error Message', 'type': 'text', 'required': False},
        ],
        'default_priority': 'medium',
        'default_category': 'software',
    },
    'account': {
        'name': 'Account Issue',
        'icon': '🔑',
        'description_guide': [
            'Username / Email:',
            'System involved:',
            'Detailed description:',
        ],
        'fields': [
            {'name': 'request_type', 'label': 'Request Type', 'type': 'select',
             'options': ['New Account', 'Password Reset', 'Access Revoked', 'Permission Change', 'Account Unlock', 'Other'],
             'required': True},
            {'name': 'username', 'label': 'Username / Email', 'type': 'text', 'required': True},
        ],
        'default_priority': 'low',
        'default_category': 'account',
    },
    'security': {
        'name': 'Security Issue',
        'icon': '🛡️',
        'description_guide': [
            'Type of security concern:',
            'Date/Time observed:',
            'Systems affected:',
            'Has this been reported elsewhere?:',
        ],
        'fields': [
            {'name': 'issue_type', 'label': 'Issue Type', 'type': 'select',
             'options': ['Phishing Report', 'Suspicious Activity', 'Vulnerability', 'Data Breach', 'Unauthorized Access', 'Other'],
             'required': True},
        ],
        'default_priority': 'critical',
        'default_category': 'security',
    },
    'other': {
        'name': 'General Inquiry',
        'icon': '📋',
        'description_guide': [
            'Describe your issue or question in detail:',
        ],
        'fields': [],
        'default_priority': 'medium',
        'default_category': 'other',
    },
}
