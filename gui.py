from flaskwebgui import FlaskUI
#from nicegui import ui
import app
#from app import app

#ui.label("Hello Super NiceGUI!")
#ui.button("BUTTON", on_click=lambda: ui.notify("button was pressed"))

#def start_nicegui(**kwargs):
#    ui.run(**kwargs)

ui = FlaskUI(app=app.app,
            #server=lambda **kwargs: ui.run(**kwargs),
            server='flask',
            #server_kwargs={"dark": True, "reload": False, "show": False, "port": 5003},
            #host="127.0.0.1:5003",
            #port=5003,
            width=800,
            height=400,
        ).run()