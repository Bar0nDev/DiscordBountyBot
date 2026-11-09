import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from utils.confirmation import ConfirmationView


class ConfirmationTests(unittest.IsolatedAsyncioTestCase):
    async def test_only_initiating_moderator_can_respond(self):
        view = ConfirmationView(author_id=1)
        response = SimpleNamespace(send_message=AsyncMock())
        with patch("utils.confirmation.has_moderator_role", return_value=True):
            other = SimpleNamespace(user=SimpleNamespace(id=2), response=response)
            self.assertFalse(await view.interaction_check(other))
            response.send_message.assert_awaited_once()
        with patch("utils.confirmation.has_moderator_role", return_value=False):
            starter = SimpleNamespace(user=SimpleNamespace(id=1), response=response)
            self.assertFalse(await view.interaction_check(starter))
        view.stop()

    async def test_second_response_cannot_change_decision(self):
        view = ConfirmationView(author_id=1)
        response = SimpleNamespace(edit_message=AsyncMock(), defer=AsyncMock())
        interaction = SimpleNamespace(response=response)
        await view.confirm.callback(interaction)
        await view.cancel.callback(interaction)
        self.assertTrue(view.confirmed)
        self.assertTrue(all(button.disabled for button in view.children))
        response.edit_message.assert_awaited_once()
        response.defer.assert_awaited_once()
