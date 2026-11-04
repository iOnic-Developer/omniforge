"""Public release identity embedded by the image build."""
import os
from datetime import datetime

VERSION = os.environ.get('OMNIFORGE_VERSION', '0.3.0')
BUILD_DATE = os.environ.get('OMNIFORGE_BUILD_DATE', '')
REVISION = os.environ.get('OMNIFORGE_REVISION', '')


def release_info() -> dict:
    try:
        display = datetime.fromisoformat(BUILD_DATE.replace('Z', '+00:00')).strftime('%d/%m')
    except ValueError:
        display = 'Development'
    return {'version': VERSION, 'build_date': BUILD_DATE or None,
            'display_date': display, 'revision': REVISION or None}
