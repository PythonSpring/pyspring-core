from py_spring_core.core.entities.bean_collection import BeanCollection
from py_spring_core.core.entities.component import Component
from py_spring_core.core.entities.controllers.rest_controller import RestController
from py_spring_core.core.entities.properties.properties import Properties

AppEntities = Component | RestController | BeanCollection | Properties
