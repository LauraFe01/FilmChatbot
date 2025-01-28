# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions

import logging
import re
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.events import SlotSet
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.events import UserUtteranceReverted
from rasa_sdk.types import DomainDict
from fuzzywuzzy import process
import pandas as pd
from rasa_sdk.events import SlotSet, AllSlotsReset, ActiveLoop


movies_df = pd.read_csv("Dataset/imdb_top_1000.csv")

actor_df = pd.concat([movies_df['Star1'], movies_df['Star2'], movies_df['Star3']]).unique()
director_df = movies_df['Director'].unique()
movies = movies_df['Series_Title'].unique()
valid_genre = ['Drama', 'Crime', 'Action', 'Adventure', 'Biography', 'History', 'Sci-Fi',
 'Romance', 'Western', 'Fantasy', 'Comedy', 'Thriller', 'Animation', 'Family',
 'War', 'Mystery', 'Music', 'Horror', 'Musical', 'Film-Noir', 'Sport']
soglia_fuzzy = 70

class ActionAskClarification(Action):
    def name(self):
        return "action_ask_clarification"

    async def run(self, dispatcher, tracker, domain):
        dispatcher.utter_message(text="Sorry, I can't understand. Could you rephrase?")
        return [UserUtteranceReverted()]


class ActionListTopMovies(Action):
    def name(self) -> Text:
        return "action_list_top_movies"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        top_movies = movies_df.sort_values(by="IMDB_Rating", ascending=False).head(10)

        response = "🎬 Here are the top-rated movies in IMDB:\n\n"
        response += "\n".join([
            f"⭐ {row['Series_Title']} - Rating: {row['IMDB_Rating']}" 
            for _, row in top_movies.iterrows()
        ])

        dispatcher.utter_message(text=response)
        return []
    

class ActionAskDirectorMovie(Action):
    def name(self) -> str:
        return "action_ask_director"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        
        movie_name = tracker.get_slot("movie")

        if not movie_name:
            dispatcher.utter_message(text="❓ Please tell me the movie you are asking about. 🎥")
            return [SlotSet('movie', None)]

        movie_row = movies_df[movies_df['Series_Title'].str.contains(movie_name, case=False, na=False)]
        
        if movie_row.empty:
            new_name, score = process.extractOne(movie_name, movies.tolist())

            if score > soglia_fuzzy:
                dispatcher.utter_message("You misspelled the name of the movie. Don't worry, I've got it! 😊✨")
                movie_row = movies_df[movies_df['Series_Title'].str.contains(new_name, case=False, na=False)]

        
        if not movie_row.empty:
            if len(movie_row) > 1:
                message = "🔍 Multiple movies found matching your query:\n"
                for _, row in movie_row.iterrows():
                    message += f"🎬 {row['Series_Title']} - Directed by {row['Director']} 🌟\n"
                dispatcher.utter_message(text=message.strip())
            else:
                director = movie_row.iloc[0]['Director']
                dispatcher.utter_message(
                    text=f"🎬 The director of {movie_row.iloc[0]['Series_Title']} is {director}. 🌟"
                )
        else:
            dispatcher.utter_message(
                text=f"😔 I'm sorry, I couldn't find the movie {movie_name} or {new_name} in my database. 📂"
            )

        return [SlotSet('movie', None)]
    
class ActionAskGenre(Action):
    def name(self) -> str:
        return "action_ask_genre"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):

        movie_name = tracker.get_slot("movie")

        if not movie_name:
            dispatcher.utter_message(text="❓ I couldn't catch the name of the movie. Can you repeat it? 🎥")
            return [SlotSet('movie', None)]


        movie_row = movies_df[movies_df['Series_Title'].str.contains(movie_name, case=False, na=False)]

        if movie_row.empty:
            new_name, score = process.extractOne(movie_name, movies.tolist())
            if score > soglia_fuzzy:
                dispatcher.utter_message("You misspelled the movie. Don't worry, I've got it! 😊✨")
                movie_row = movies_df[movies_df['Series_Title'].str.contains(new_name, case=False, na=False)]


        if not movie_row.empty:
            alternatives = [
                f"🎞️ {row['Series_Title']} - Genre: {row['Genre']}" 
                for _, row in movie_row.iterrows()
            ]
            response = "🎬 Here are the genres for the matching movies:\n\n" + "\n".join(alternatives)
            dispatcher.utter_message(text=response)
        else:
            dispatcher.utter_message(
                text=f"😔 I'm sorry, I couldn't find the movie '{movie_name}' or '{new_name}' in my database. 📂"
            )

        return [SlotSet('movie', None)]
    
class ActionAskDirector(Action):
    def name(self) -> str:
        return "action_movies_by_director"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        
        director = tracker.get_slot("director")
        
        if not director:
            dispatcher.utter_message(text="🎬 I couldn't catch the name of the director. Can you repeat it?")
            return [SlotSet('director', None)]

        
        dir_movies = movies_df[movies_df['Director'].str.contains(director, case=False, na=False)]
        
        if dir_movies.empty:
            if len(director.split()) > 1:
                new_name, score = process.extractOne(director, director_df.tolist())
                director = new_name
            elif len(director.split()) == 1:
                new_name, score = process.extractOne(director, [s.split()[-1] if len(s.split()) > 1 else "" for s in director_df.tolist()])
                director = new_name

            if score > soglia_fuzzy:
                dispatcher.utter_message(text=f"Did you mean '{director}'? Don't worry, I've found the information for you! 😊")
                dir_movies = movies_df[movies_df['Director'].str.contains(new_name, case=False, na=False)]
                

        if not dir_movies.empty:
           
            matching_directors = dir_movies[['Director']].stack().unique()
            director_with_same_surname = [name for name in matching_directors if name.split()[-1].lower() == director.split()[-1].lower()]

            if len(director_with_same_surname) == 0:
                dispatcher.utter_message(text="Wait a moment 🤔. You need to provide either the full name or just the last word of the name (surname).")
                return [SlotSet('director', None)]
            
            if len(set(director_with_same_surname)) > 1:
                
                dispatcher.utter_message(
                    text=f"There are multiple directors with the surname '{director.split()[-1]}'. Please be more specific:\n" +
                        "\n".join([f"👤 {director}" for director in director_with_same_surname])
                )
                return [SlotSet('director', None)]
            
            full_name = next((name for name in matching_directors if director.lower() in name.lower()), director)

            movie_list = dir_movies['Series_Title'].tolist()
            movie_titles = '\n'.join([f"🎞️ {movie}" for movie in movie_list])  # Aggiungi un'icona a ogni titolo
            dispatcher.utter_message(
                text=f"🎥 The movies made by {full_name} are:\n{movie_titles}"
            )
        else:
            dispatcher.utter_message(
                text=f"😔 I'm sorry, I couldn't find any films by {tracker.get_slot('director')} or {new_name} in my database."
            )
        
        return [SlotSet('director', None)]


class ActionAskActor(Action):
    def name(self) -> str:
        return "action_movies_by_actor"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict):
        
        actor_name = tracker.get_slot("actor")
        original_actor_name = actor_name 
        if not actor_name:
            dispatcher.utter_message(text="I couldn't catch the name of the actor. Can you repeat it?")
            return [SlotSet('actor', None)]

        actor_movies = movies_df[
            (movies_df['Star1'].str.contains(actor_name, case=False, na=False)) |
            (movies_df['Star2'].str.contains(actor_name, case=False, na=False)) |
            (movies_df['Star3'].str.contains(actor_name, case=False, na=False)) |
            (movies_df['Star4'].str.contains(actor_name, case=False, na=False))
        ]

        if actor_movies.empty:
            # Utilizziamo il fuzzy matching per correggere eventuali errori
            all_actors = (
                movies_df['Star1'].dropna().tolist() +
                movies_df['Star2'].dropna().tolist() +
                movies_df['Star3'].dropna().tolist() +
                movies_df['Star4'].dropna().tolist()
            )
            all_actors = list(set(all_actors))
            if len(actor_name.split())>1:
                corrected_name, score = process.extractOne(actor_name, all_actors)
            elif len(actor_name.split())==1:
                all_actor_surname = [s.split()[-1] if len(s.split()) > 1 else "" for s in all_actors]
                corrected_name, score = process.extractOne(actor_name, all_actor_surname)

            if score > soglia_fuzzy:  # Soglia per considerare una correzione accettabile
                actor_name = corrected_name
                dispatcher.utter_message(text=f"Did you mean '{actor_name}'? Don't worry, I've found the information for you! 😊")
                actor_movies = movies_df[
                    (movies_df['Star1'].str.contains(actor_name, case=False, na=False)) |
                    (movies_df['Star2'].str.contains(actor_name, case=False, na=False)) |
                    (movies_df['Star3'].str.contains(actor_name, case=False, na=False)) |
                    (movies_df['Star4'].str.contains(actor_name, case=False, na=False))
                ]

        if not actor_movies.empty:
            matching_actors = actor_movies[['Star1', 'Star2', 'Star3', 'Star4']].stack().unique()
            actors_with_same_surname = [
                name for name in matching_actors 
                if name.split()[-1].lower() == actor_name.split()[-1].lower()
            ]
            if len(actors_with_same_surname) == 0:
                dispatcher.utter_message(text="Wait a moment 🤔. You need to provide either the full name or just the last word of the name (surname).")
                return [SlotSet('actor', None)]
            
            if len(set(actors_with_same_surname)) > 1:
            
                dispatcher.utter_message(
                    text=f"There are multiple actors with the surname '{actor_name.split()[-1]}'. Please be more specific and try again:\n" +
                        "\n".join([f"👤 {actor}" for actor in actors_with_same_surname])
                )
                return [SlotSet('actor', None)]
            
            full_name = next((name for name in matching_actors if actor_name.lower() in name.lower()), actor_name)
            
            movie_list = actor_movies['Series_Title'].tolist()
            movie_titles = '\n'.join([f"🎬 {movie}" for movie in movie_list])  
            dispatcher.utter_message(text=f"🌟 The films featuring {full_name} are:\n{movie_titles}")
        else:
            dispatcher.utter_message(text=f"😔 I'm sorry, I couldn't find any films featuring '{original_actor_name}' or '{actor_name}' in my database.")

        return [SlotSet('actor', None)]



class ActionAskMovieInfo(Action):
    def name(self) -> str:
        return "action_ask_movie_info"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        movie_name = tracker.get_slot("movie")
        first_name = movie_name

        if not movie_name:
            dispatcher.utter_message(text="I couldn't catch the name of the movie. Can you repeat it?")
            return [SlotSet('movie', None)]

        movie_row = movies_df[movies_df['Series_Title'].str.contains(movie_name, case=False, na=False)]

        if movie_row.empty:         
            new_name, score = process.extractOne(movie_name, movies_df['Series_Title'].tolist())
            if score > soglia_fuzzy:
                dispatcher.utter_message(f"You misspelled the title. Don't worry, I've got it! You mean {new_name} 😊✨")
                movie_row = movies_df[movies_df['Series_Title'].str.contains(new_name, case=False, na=False)]

        if not movie_row.empty:
            movie = movie_row.iloc[0]
            title = movie['Series_Title']
            genre = movie['Genre']
            year = movie['Released_Year']
            rating = movie['IMDB_Rating']
            overview = movie['Overview']
            director = movie['Director']
            stars = movie[['Star1', 'Star2', 'Star3', 'Star4']].dropna().values
            runtime = movie['Runtime']

            stars_list = ', '.join(stars) if len(stars) > 0 else "No stars listed."

            response = (
                f"🎥 Here are the details for the movie with the best matching'\n"
                f"📽️ Title: {title}\n"
                f"🎭 Genre: {genre}\n"
                f"⏳ Runtime: {runtime}\n"
                f"📅 Release Year: {year}\n"
                f"⭐ Rating: {rating}/10\n"
                f"🎬 Director: {director}\n"
                f"🌟 Stars: {stars_list}\n"
                f"📝 Overview: {overview}"
            )


            dispatcher.utter_message(text=response)
            dispatcher.utter_message(image=movie['Poster_Link'])
        else:
            dispatcher.utter_message(text=f"I'm sorry, I couldn't find any information about the movie '{first_name}' or '{movie_name}' in my database.")

        return [SlotSet('movie', None)]

class ActionCountFilms(Action):
    def name(self) -> str:
        return "action_count_films"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict) -> list:
        form_author = tracker.get_slot("form_author")
        form_quality = tracker.get_slot("form_quality") or "none"
        
        all_directors = movies_df['Director'].unique()
        filtered_movies = movies_df[movies_df['Director'].str.contains(form_author, case=False, na=False)]
        
        if filtered_movies.empty:
            if len(form_author.split()) > 1:
                new_name, score = process.extractOne(form_author, all_directors)
                form_author = new_name
                
            elif len(form_author.split()) == 1:
                new_name, score = process.extractOne(form_author, [s.split()[-1] if len(s.split()) > 1 else "" for s in all_directors.tolist()])
                form_author = new_name
               
            if score > soglia_fuzzy:
                dispatcher.utter_message(text=f"Did you mean '{form_author}'? Don't worry, I've found the information for you! 😊")
                filtered_movies = movies_df[movies_df['Director'].str.contains(form_author, case=False, na=False)]
                
            else:
                dispatcher.utter_message(
                    text=f"😔 Sorry, no director matching '{form_author}' was found."
                )
                return [SlotSet("form_author", None), SlotSet("form_quality", None)]
        
        if not filtered_movies.empty:
            # Caso in cui si sono piu autori che hanno lo stesso cognome(ultima parte del nominativo)
            matching_directors = filtered_movies[['Director']].stack().unique()
            director_with_same_surname = [name for name in matching_directors if name.split()[-1].lower() == form_author.split()[-1].lower()]

            if len(director_with_same_surname) == 0:
                dispatcher.utter_message(text="Wait a moment 🤔. You need to provide either the full name or just the last word of the name (surname).")
                return [SlotSet("form_author", None), SlotSet("form_quality", None)]
            
            if len(set(director_with_same_surname)) > 1:
                dispatcher.utter_message(
                    text=f"There are multiple directors with the surname '{form_author.split()[-1]}'. Rephrase your question and then include the specific director's name:\n" +
                        "\n".join([f"👤 {directorr}" for directorr in director_with_same_surname])
                )
                return [SlotSet("form_author", None), SlotSet("form_quality", None)]

        
        full_name = next((name for name in matching_directors if form_author.lower() in name.lower()), form_author)

        if form_quality == "none":
            filtered_movies = movies_df[movies_df['Director'] == full_name]
            
            num_films = len(filtered_movies)
            if not filtered_movies.empty:
                filtered_movies = filtered_movies.sort_values(by=['IMDB_Rating'], ascending=[False])
                dispatcher.utter_message(
                    text=f"🎬 The number of films by {full_name} are {num_films}.\n"
                )
                for _, row in filtered_movies.iterrows():
                    dispatcher.utter_message(
                        text=f"🎞️ Movie: {row['Series_Title']}\n⭐ Rating: {row['IMDB_Rating']}",
                        image=row['Poster_Link']
                    )
            else:
                dispatcher.utter_message(
                    text=f"😔 Sorry, no films found for {full_name}."
                )
        else:
            form_quality = float(form_quality)
            filtered_movies = movies_df[
                (movies_df['Director'] == full_name) &
                (movies_df['IMDB_Rating'] >= form_quality)
            ]
            num_films = len(filtered_movies)
            if not filtered_movies.empty:
                filtered_movies = filtered_movies.sort_values(by=['IMDB_Rating'], ascending=[False])
                dispatcher.utter_message(
                    text=f"🎥 The number of films by {full_name} with a rating higher than {form_quality} are {num_films}."
                )
                for _, row in filtered_movies.iterrows():
                    dispatcher.utter_message(
                        text=f"🎞️ Film: {row['Series_Title']}\n⭐ Rating: {row['IMDB_Rating']}",
                        image=row['Poster_Link']
                    )
            else:
                dispatcher.utter_message(
                    text=f"😔 Sorry, no films by {full_name} with a rating higher than {form_quality} were found."
                )

        return [SlotSet("form_author", None),
                SlotSet("form_quality", None)]

        
class ActionCheckFormSlots(Action):

    def name(self) -> str:
        return "action_check_form_slots"
    
    def run(self, dispatcher, tracker, domain):
        form_director_genre = tracker.get_slot('form_director_genre')
        form_quality = tracker.get_slot('form_quality')

        if form_director_genre is None:
            form_director_genre = "None"
        if form_quality is None:
            form_quality = "None"

        return [SlotSet("form_director_genre", form_director_genre),
                SlotSet("form_quality", form_quality)]
    

class ActionResetDirectorForm(Action):
    def name(self) -> Text:
        return "action_reset_director_form"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        return [SlotSet("form_author", None),
                SlotSet("form_quality", None)]
    
class ValidateFilmCountForm(FormValidationAction):
    def name(self) -> str:
        return "validate_film_count_form"

    async def validate_form_author(
    self, value: str, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
) -> dict:

        if isinstance(value, str) and value.strip():
            if re.search(r"\d", value):
                dispatcher.utter_message(text="⚠️ The author's name should not contain numbers. Please try again.")

                if tracker.get_slot("form_quality") is not None:
                    dispatcher.utter_message(text="❌ Please provide one slot at a time")
                    return {"form_quality": None, "form_author": value}
                
                return {"form_author": None}
            else:

                if tracker.get_slot("form_quality") is not None:
                    dispatcher.utter_message(text="❌ Please provide one slot at a time")
                    return {"form_quality": None, "form_author": value}
                
                return {"form_author": value}
        else:
            dispatcher.utter_message(text="⚠️ Please provide a valid author name.")
            return {"form_author": None}

    async def validate_form_quality(
        self, value: str, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
    ) -> dict:

        
        if tracker.get_slot("form_author") is None:
            dispatcher.utter_message(text="❌ Please provide a single slot.")
            return {"form_quality": None}

        if value == "none" or value is None:
            return {"form_quality": value}

        value = value.replace(",", ".")

        try:
            rating = float(value) 
            if 0.0 <= rating <= 10.0:
                return {"form_quality": rating}
            else:
                dispatcher.utter_message(
                    text="⭐ The rating must be between 0 and 10. Please try again."
                )
        except ValueError:
            dispatcher.utter_message(
                text="⭐ Please provide a valid rating between 0 and 10 (e.g., 8 or 8.5)."
            )

        return {"form_quality": None} 

class ActionProvideMovieRecommendation(Action):
    def name(self) -> Text:
        return "action_provide_movie_recommendation"

    def run(
        self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        
        min_release_year = tracker.get_slot("min_release_year")
        genre = tracker.get_slot("form_genre")  
        min_rating = tracker.get_slot("form_quality")

        if not (min_release_year and genre and min_rating):
            dispatcher.utter_message(text="⚠️ It seems like some information is missing. Please try again.")
            return []

        if isinstance(genre, list):
            genre = "".join(f"(?=.*{genree})" for genree in genre)

        filtered_movies = self.filter_movies(min_release_year, genre, min_rating)

        if not filtered_movies.empty:
            dispatcher.utter_message(text="🎬 Here are some movies I recommend based on your preferences:")
            for _, row in filtered_movies.iterrows():
                dispatcher.utter_message(
                    text=(
                        f"📽️ Title: {row['Series_Title']} ({row['Released_Year']})\n"
                        f"⭐ Rating: {row['IMDB_Rating']}\n"
                        f"🎭 Genre: {row['Genre']}"
                    ),
                    image=row.get("Poster_Link", None),
                )
        else:
            dispatcher.utter_message(
                text="😔 Sorry, I couldn't find any movies matching your preferences. Try adjusting the criteria!"
            )

        return self.reset_slots()

    def filter_movies(self, min_release_year, genre, min_rating):
            
            movies_df["Released_Year"] = pd.to_numeric(movies_df["Released_Year"], errors="coerce").fillna(0).astype(int)
            filtered_movies = movies_df[
                (movies_df["Released_Year"] >= min_release_year if min_release_year else True)
                & (movies_df["Genre"].str.contains(genre, case=False, na=False) if genre else True)
                & (movies_df["IMDB_Rating"] >= min_rating if min_rating else True)
            ].head(10)
            filtered_movies = filtered_movies.sort_values(by=['Released_Year', 'IMDB_Rating'], ascending=[False, False])
            return filtered_movies


    def reset_slots(self):

        return [
            SlotSet("min_release_year", None),
            SlotSet("form_genre", None),
            SlotSet("form_quality", None),
        ]

class ActionResetMoviePreferences(Action):
    def name(self) -> Text:
        return "action_reset_movie_preferences"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:
        
        return [
            SlotSet("min_release_year", None),
            SlotSet("form_genre", None),
            SlotSet("form_quality", None)
        ]

class ValidateMovieRecommendationForm(FormValidationAction):
    def name(self) -> str:
        return "validate_movie_recommendation_form"

    async def validate_min_release_year(
        self, value, dispatcher, tracker, domain
    ) -> Dict[Text, Any]:
        return {"min_release_year": tracker.get_slot("min_release_year")}

    async def validate_form_genre(
    self, value: str, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
) -> dict:
        
        valid_genres = [g.lower() for g in valid_genre]
        
        if tracker.get_slot("form_quality") is not None:
            dispatcher.utter_message(text="❌ Please provide a single slot.")
            return {"form_quality": None}

        if isinstance(value, list):
            genres = [genre.strip().lower() for genre in value]
        else:
            genres = [genre.strip().lower() for genre in value.split(",")]

        invalid_genres = [genre for genre in genres if genre not in valid_genres]

        if not invalid_genres:
            return {"form_genre": genres}
        else:
            dispatcher.utter_message(
                text=f"⚠️ The following genres are not valid: {', '.join(invalid_genres)}. Please choose from: {', '.join(valid_genres)}."
            )
            return {"form_genre": None} 

    async def validate_form_quality(
        self, value: str, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
    ) -> dict:
        
        if tracker.get_slot("form_genre") is None:
            dispatcher.utter_message(text="❌ Please provide the genre before entering the rating.")
            return {"form_quality": None}

        if value == "none" or value is None:
            return {"form_quality": value}

        value = value.replace(",", ".")

        try:
            rating = float(value)
            if 0.0 <= rating <= 10.0:
                return {"form_quality": rating}
            else:
                dispatcher.utter_message(
                    text="⭐ The rating must be between 0 and 10. Please try again."
                )
        except ValueError:
            dispatcher.utter_message(
                text="⭐ Please provide a valid rating between 0 and 10 (e.g., 8 or 8.5)."
            )

        return {"form_quality": None}

class ValidateGrossVotesRecommendationForm(FormValidationAction):
    def name(self) -> str:
        return "validate_gross_votes_recommendation_form"

    async def validate_form_votes(
        self, value: str, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
    ) -> dict:
        
        value = str(tracker.get_slot("form_votes"))
        
        if re.fullmatch(r"^\d+$", value):
            try:
                votes = int(value)
                if votes > 0:
                    return {"form_votes": votes}
                else:
                    dispatcher.utter_message(text="⚠️ The number of votes must be a positive integer. Please try again.")
            except ValueError:
                dispatcher.utter_message(text="⚠️ An unexpected error occurred. Please try again.")
        else:
            dispatcher.utter_message(text="⚠️ Please provide a valid positive integer for the number of votes.")

        return {"form_votes": None}

    async def validate_form_gross(
        self, value: str, dispatcher: CollectingDispatcher, tracker: Tracker, domain: dict
    ) -> dict:
        
        return {"form_gross": tracker.get_slot("form_gross")} 
        

class ActionGrossVotesRecommendation(Action):
    def name(self) -> Text:
        return "action_gross_votes_recommendation"

    def run(self, dispatcher: CollectingDispatcher, 
            tracker: Tracker, 
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        votes_threshold = tracker.get_slot("form_votes")
        gross_threshold = tracker.get_slot("form_gross")

        try:
            votes_threshold = int(votes_threshold)
            gross_threshold = float(gross_threshold)
        except (ValueError, TypeError):
            dispatcher.utter_message(
                text="🚨 The values entered for votes or gross are invalid. Please use numbers (Decimal separator: '.')"
            )
            return []

        movies_df["Gross"] = movies_df["Gross"].replace({',': ''}, regex=True)
        movies_df["Gross"] = pd.to_numeric(movies_df["Gross"], errors='coerce')

        
        filtered_movies = movies_df[
            (movies_df['No_of_Votes'] >= votes_threshold) & 
            (movies_df['Gross'] >= gross_threshold)
        ].dropna(subset=['Series_Title', 'No_of_Votes', 'Gross'])

        filtered_movies = filtered_movies.head(10)
        filtered_movies = filtered_movies.sort_values(by=['No_of_Votes', 'Gross'], ascending=[False, False])
        if not filtered_movies.empty:
            dispatcher.utter_message(text="🎥 Here are the top 10 films that match your criteria:")
            for _, movie in filtered_movies.iterrows():
                message = (
                    f"• {movie['Series_Title']}\n"
                    f"   - Votes: {movie['No_of_Votes']} (based on reviews)\n"
                    f"   - Gross: ${movie['Gross']}\n"
                )
                dispatcher.utter_message(text=message, image=movie['Poster_Link'])
            
        else:
            dispatcher.utter_message(
                text=f"😔 Sorry, I couldn't find any movies with at least {votes_threshold} votes and ${gross_threshold} gross."
            )

        return [SlotSet("form_votes", None), SlotSet("form_gross", None)]


class ActionResetGrossVotesRecommendationForm(Action):
    def name(self) -> Text:
        return "action_reset_gross_votes_recommendation_form"

    def run(self, dispatcher, tracker, domain) -> List[Dict[Text, Any]]:  
        return [SlotSet("form_votes", None),
                SlotSet("form_gross", None)]
    

class ActionRemoveUnnecessarySlots(Action):
    def name(self) -> Text:
        return "action_remove_unnecessary_slots"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[SlotSet]:
        unnecessary_slots = ["form_author", "form_genre", "movie" ]

        events = []
        for slot in unnecessary_slots:
            if tracker.get_slot(slot) is not None:
                events.append(SlotSet(slot, None))
        
        return events
    
class ActionResumeFormMovieReccomendation(Action):
    def name(self):
        return "action_resume_form_movie_reccomendation"

    def run(self, dispatcher, tracker, domain):
        
        dispatcher.utter_message(text="🔄 Let's pick up where we left off! 😊")
        return [ActiveLoop("movie_recommendation_form")]
    
class ActionResumeFormMovieCount(Action):
    def name(self):
        return "action_resume_form_movie_count"

    def run(self, dispatcher, tracker, domain):
       
        dispatcher.utter_message(text="🔄 Let's pick up where we left off! 😊")
        return [ActiveLoop("film_count_form")]
    
class ActionResumeFormGrossMovie(Action):
    def name(self):
        return "action_resume_form_movie_gross"

    def run(self, dispatcher, tracker, domain):
       
        dispatcher.utter_message(text="🔄 Let's pick up where we left off! 😊")
        return [ActiveLoop("gross_votes_recommendation_form")]
