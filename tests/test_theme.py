from website_blocker.theme import menu_stylesheet, stylesheet


def test_detached_tray_menu_has_explicit_item_colors():
    css = menu_stylesheet("dark", "violet")
    assert "QMenu::item" in css
    assert "color: #F4F3FA" in css
    assert "background-color: #13151F" in css


def test_light_theme_uses_light_app_surfaces():
    css = stylesheet("violet", "light")
    assert "background-color: #F5F6FA" in css
    assert "background-color: #FFFFFF" in css
    assert "color: #20212A" in css

