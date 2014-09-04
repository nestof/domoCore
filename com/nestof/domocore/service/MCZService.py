'''
Created on 22 mai 2014

@author: nestof
'''

import logging
from os.path import os

import __main__
from com.nestof.domocore import enumeration
from com.nestof.domocore.service.DatabaseService import DatabaseService
from com.nestof.domocore.service.MCZProtocolService import MCZProtocolService


class MCZService(object):
    '''
    classdocs
    '''


    def __init__(self, database):
        '''
        Constructor
        '''
        self.logger = logging.getLogger(__name__)
        """ Services """    
        self.databaseService = DatabaseService(database)
        self.tempService = __main__.tempService
        self.config = __main__.config
        self.mczProtocolService = MCZProtocolService(database)

        
    def launchAuto(self):
        """ Current Mode"""    
        currentMode = self.databaseService.findCurrentMode()
    
        onPeriode = currentMode != None
    
        """ Last mode id """
        lastModeId = self.databaseService.getLastModeId()   
    
        """ Stove state"""
        stoveIsOn = self.databaseService.getStoveActive()    
        
        """ Forced flags""" 
        onForced = self.databaseService.getForcedOn()
        offForced = self.databaseService.getForcedOff()
        
        """ Forced mode """
        forcedMode = self.databaseService.findForcedMode()
        
        """ The current temp """    
        currentTemp = self.tempService.readTemp();
        
        """ current mode temp zones"""
        if onPeriode :        
            tempZone1 = currentTemp < currentMode._cons
            tempZone3 = currentTemp >= currentMode._max
            tempZone2 = not tempZone1 and not tempZone3
        
        """ forced mode temp zones"""
        tempForcedZone1 = currentTemp < forcedMode._cons
        tempForcedZone3 = currentTemp >= forcedMode._max
        tempForcedZone2 = not tempForcedZone1 and not tempForcedZone3
        
        """ initialization """ 
        startStove = False
        shutdownStove = False
            
        niveauPuissance = enumeration.NiveauPuissance.niveau1
        niveauVentilation = enumeration.NiveauVentilation.auto
        trameMode = enumeration.Mode.automatique
        trameEtat = enumeration.Etat.off
        trameActionneur = enumeration.Actionneur.systeme
        
        
        """ ------- DEBUG ------ """
        if onPeriode :
            print("  Mode en cours   : " + currentMode._libelle)
            print("  Consigne        : " + str(currentMode._cons) + "°C")
            print("  Max             : " + str(currentMode._max) + "°C")
        print("  Dernier mode    : " + str(lastModeId))
        print("  Poêle actif     : " + str(stoveIsOn))
        print("  Marche forcée   : " + str(onForced))
        print("  Arrêt forcé     : " + str(offForced))
        print("  Température     : " + str(currentTemp) + "°C")
        """ ------- DEBUG ------ """
        
        """RAZ forced flags"""
        if (onForced and offForced) :
            self.databaseService.setForcedOff(False)
            self.databaseService.setForcedOn(False)
            onForced = False
            offForced = False
        elif lastModeId != None and currentMode != None and str(currentMode._id) != str(lastModeId) :
            """ On change de mode => RAZ des flags """
            self.databaseService.setForcedOff(False)
            self.databaseService.setForcedOn(False)
            onForced = False
            offForced = False
        elif (offForced and not onPeriode):
            """ On est en arrêt forcé et en période d'arrêt => RAZ flag arrêt forcé """
            self.databaseService.setForcedOff(False)
            offForced = False
            None
        elif (onForced and onPeriode):
            """ On est en marche forcée et en période de fonctionnement """
            if stoveIsOn :
                """ Le poêle est allumé => RAZ flag marche forcée """
                self.databaseService.setForcedOn(False)
                onForced = False
            elif tempZone1 or tempZone3 :
                """ Le poêle est éteint est on est dans les zones de température 1 ou 3 => RAZ flag marche forcée """
                self.databaseService.setForcedOn(False)
                onForced = False
        """Mise à jour dernier mode"""
        self.databaseService.setLastModeId(currentMode._id)
        
                      
        """ Start / Continue cases"""
        if onPeriode:
            if (not onForced and not offForced and tempZone1) or (not onForced and not offForced and tempZone2 and stoveIsOn) or (not stoveIsOn and onForced and tempZone2):
                niveauPuissance = self.mczProtocolService.getNiveauPuissance(currentTemp, currentMode._cons);
                startStove = True
        elif onForced and (tempForcedZone1 or tempForcedZone2) :
            if tempForcedZone1 :
                niveauPuissance = self.mczProtocolService.getNiveauPuissance(currentTemp, forcedMode._cons);
                startStove = True
        
        if startStove:
            trameEtat = enumeration.Etat.on
            if onForced and not stoveIsOn :
                trameActionneur = enumeration.Actionneur.utilisateur
        else : 
            """ Stop cases """    
            if stoveIsOn :
                if (not onPeriode and not onForced and not offForced) or (onPeriode and not onForced and offForced) or (onPeriode and not onForced and not offForced and tempZone3) or (not onPeriode and onForced and not offForced and tempForcedZone3) :
                    shutdownStove = True
            else :
                shutdownStove = True 
            
        if shutdownStove :
            trameEtat = enumeration.Etat.off
            lastTrame = self.mczProtocolService.getLastTrame()
            if lastTrame != None :
                niveauPuissance = lastTrame._puissance
                niveauVentilation = lastTrame._ventilation
            if offForced and stoveIsOn:
                trameActionneur = enumeration.Actionneur.utilisateur
    
        print("  startStove      : " + str(startStove))
        print("  shutdownStove   : " + str(shutdownStove))
        
       
       
        if startStove or shutdownStove :
            self.constructAndSendTrame(startStove, shutdownStove, trameEtat, trameMode, trameActionneur, niveauPuissance, niveauVentilation)
        
    def launchManu(self):
        """Récupérer valeurs de ordre manu"""
        """Si ordre marche et T°courante < T°max mode manu alors envoyer ordre On"""
        """Sinon envoyer ordre Off"""
        """------------------------"""
        
        """ initialization """ 
        startStove = False
        shutdownStove = False
            
        niveauPuissance = enumeration.NiveauPuissance.niveau1
        niveauVentilation = enumeration.NiveauVentilation.auto
        trameMode = enumeration.Mode.automatique
        trameEtat = enumeration.Etat.off
        trameActionneur = enumeration.Actionneur.systeme
        
        """Manual Order"""
        manualOrder = self.databaseService.getOrdreManu()
        
        """Is stove On """
        stoveIsOn = self.databaseService.getStoveActive()
        
        """ The current temperature """    
        currentTemp = self.tempService.readTemp()
        
        """ Parametered temperatures """
        manualMode = self.databaseService.findManualMode()
        
        """ Manual mode temperature zones"""
        tempManualZone1 = currentTemp < manualMode._cons
        tempManualZone3 = currentTemp >= manualMode._max
        tempManualZone2 = not tempManualZone1 and not tempManualZone3
        
        """ ------- DEBUG ------ """
        print("  Consigne        : " + str(manualMode._cons) + "°C")
        print("  Max             : " + str(manualMode._max) + "°C")
        print("  Poêle actif     : " + str(stoveIsOn))
        print("  Ordre manuel    : " + str(manualOrder.value))
        print("  Température     : " + str(currentTemp) + "°C")
        """ ------- DEBUG ------ """
        
        
        """Start/ Continue cases """
        if manualOrder == enumeration.OrdreManuel.marche and tempManualZone1 or (stoveIsOn and tempManualZone2):
            niveauPuissance = self.mczProtocolService.getNiveauPuissance(currentTemp, manualMode._cons);
            startStove = True
            trameEtat = enumeration.Etat.on
            if not stoveIsOn :
                trameActionneur = enumeration.Actionneur.utilisateur


        
        """Stop cases"""
        if manualOrder == enumeration.OrdreManuel.arret or (not startStove):
            shutdownStove = True
            trameEtat = enumeration.Etat.off
            lastTrame = self.mczProtocolService.getLastTrame()
            if lastTrame != None :
                niveauPuissance = lastTrame._puissance
                niveauVentilation = lastTrame._ventilation
            if stoveIsOn and not tempManualZone3:
                trameActionneur = enumeration.Actionneur.utilisateur
            
        print("  startStove      : " + str(startStove))
        print("  shutdownStove   : " + str(shutdownStove))
                      
        if startStove or shutdownStove :
            self.constructAndSendTrame(startStove, shutdownStove, trameEtat, trameMode, trameActionneur, niveauPuissance, niveauVentilation)

            
        
    def launchStop(self):
        """Envoyer odre Off"""
        None
        
    def constructAndSendTrame(self, startStove, shutdownStove, trameEtat, trameMode, trameActionneur, niveauPuissance, niveauVentilation):
        print("  **Construction trame**")
        print("  Etat            : " + trameEtat.name)
        print("  Mode            : " + trameMode.name)
        print("  Actionneur      : " + trameActionneur.name)
        print("  Puissance       : " + niveauPuissance.name)
        print("  Ventilation     : " + niveauVentilation.name)
            
        trame = self.mczProtocolService.getTrame(trameMode, trameEtat, trameActionneur, niveauPuissance, niveauVentilation)
            
        lastTrameIsSame = self.mczProtocolService.isTrameSameAsLastTrame(trame)
        lastTrameElapsesTime = self.mczProtocolService.getLastTrameElapsedTime()
            
        print("  Dernière trame identique : " + str(lastTrameIsSame))
        print("  Temps écoulé : " + str(lastTrameElapsesTime) + " minutes")
    
    
        if (not lastTrameIsSame or (lastTrameIsSame and ((startStove and lastTrameElapsesTime >= float(self.config['EMMITTER']['emmitter.same.trame.start.delay'])) or (shutdownStove and lastTrameElapsesTime >= float(self.config['EMMITTER']['emmitter.same.trame.stop.delay']))))) :
            """ Ici trame différente de la précédente ou Trame de mise en marche avec un délai >= 15 min ou Trame de mise en arrêt avec un délai >= 5 min  """
            print("  On envoie")                
            try:
                """Envoi de la trame"""
                os.system(self.config['EMMITTER']['emmitter.command'] + " " + trame._message)
                if startStove : 
                    self.databaseService.setStoveActive(True)
                else :
                    self.databaseService.setStoveActive(False)
                self.mczProtocolService.saveTrame(trame)        
            except Exception as e:
                # TODO ajouter log en base
                raise
            finally:
                None
        else :
            print("  Même trame, délai insuffisant :" + str(lastTrameElapsesTime))      
