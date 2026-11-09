import discord

from utils import has_moderator_role


class ConfirmationView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=60)
        self.author_id = author_id
        self.confirmed = False
        self.decided = False

    async def interaction_check(self, interaction):
        if interaction.user.id == self.author_id and has_moderator_role(interaction.user):
            return True
        await interaction.response.send_message(
            "Only the moderator who started this action can confirm or cancel it.",
            ephemeral=True,
        )
        return False

    def disable_buttons(self):
        for button in self.children:
            button.disabled = True

    async def decide(self, interaction, confirmed):
        if self.decided:
            await interaction.response.defer()
            return
        self.decided = True
        self.disable_buttons()
        try:
            await interaction.response.edit_message(view=self)
            self.confirmed = confirmed
        finally:
            self.stop()

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction, button):
        await self.decide(interaction, True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction, button):
        await self.decide(interaction, False)

    async def on_timeout(self):
        self.decided = True
        self.disable_buttons()


async def confirm_action(ctx, embed):
    """Wait for the initiating moderator's decision and report cancellation."""
    embed.set_footer(text="Use the buttons below to confirm or cancel.")
    view = ConfirmationView(ctx.author.id)
    message = await ctx.send(embed=embed, view=view)
    if await view.wait():
        view.disable_buttons()
        try:
            await message.edit(view=view)
        except discord.HTTPException:
            pass
        await ctx.send("Confirmation timed out.")
        return False
    if not view.confirmed:
        await ctx.send("Canceled request.")
    return view.confirmed
