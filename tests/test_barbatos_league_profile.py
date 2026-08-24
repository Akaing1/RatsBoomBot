from bot.channels.barbatos2upusr3x.games.league import Barbatos2upusr3xLeagueCommands
from bot.channels.barbatos2upusr3x.profile import BARBATOS2UPUSR3X_PROFILE


def test_barbatos_profile_configures_league_commands() -> None:
    league = BARBATOS2UPUSR3X_PROFILE.league

    assert Barbatos2upusr3xLeagueCommands in BARBATOS2UPUSR3X_PROFILE.components
    assert league.enabled is True
    assert league.provider == "opgg"
    assert league.game_name == "Barbatos2upusRex"
    assert league.tag_line == "1314"
    assert league.region == "NA"
    assert league.display_name == "Barbatos"
