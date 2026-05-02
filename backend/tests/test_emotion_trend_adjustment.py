import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import models
from app.routers import student


def test_liming_pre_0409_emotion_trend_is_steeper():
    user = models.User(username="student", name="李明", role="student")
    original = 62
    before_0409 = datetime(2026, 4, 8, 10, 0, 0)
    adjusted = student._adjust_liming_emotion_index(original, before_0409, user)
    assert adjusted > original


def test_liming_after_0409_emotion_trend_not_changed():
    user = models.User(username="student", name="李明", role="student")
    original = 62
    after_0409 = datetime(2026, 4, 10, 10, 0, 0)
    adjusted = student._adjust_liming_emotion_index(original, after_0409, user)
    assert adjusted == original


def test_other_user_emotion_trend_not_changed():
    user = models.User(username="student2", name="张伟", role="student")
    original = 38
    before_0409 = datetime(2026, 4, 8, 10, 0, 0)
    adjusted = student._adjust_liming_emotion_index(original, before_0409, user)
    assert adjusted == original
