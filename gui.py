from flaskwebgui import FlaskUI
from nicegui import ui
from app import app

ui.label("Hello Super NiceGUI!")
ui.button("BUTTON", on_click=lambda: ui.notify("button was pressed"))



def start_nicegui(**kwargs):
    ui.run(**kwargs)

gui = FlaskUI(
            server=lambda **kwargs: ui.run(**kwargs),
            server_kwargs={"dark": True, "reload": False, "show": False, "port": 5003},
            width=800,
            height=600,
        ).run()