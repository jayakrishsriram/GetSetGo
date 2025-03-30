import streamlit as st
from agno.agent import Agent
from agno.models.groq import Groq
from textwrap import dedent
from agno.tools.serpapi import SerpApiTools
from dotenv import load_dotenv
import os
import base64
import requests
import json
from datetime import datetime
from google import genai
from google.genai import types
import time
import random
from airport_data import AIRPORTS
from google.genai.types import Tool, GenerateContentConfig, GoogleSearch
from auth import check_authentication

groq_api_key = st.secrets["GROQ_API_KEY"]
serp_api_key = st.secrets["SERP_API_KEY"]
gemini_api_key = st.secrets["GEMINI_API_KEY"]

# Check authentication before showing app content
if not check_authentication():
    st.stop()

# Welcome message with user name
st.title(f"Welcome to GetSetGo, {st.session_state['user_name']}! ✈️")
st.caption("Plan your next International Travel with AI Travel Planner by researching and planning a personalized itinerary")

# Reorder sidebar elements
st.sidebar.header("🧭 TRAVEL")
page = st.sidebar.radio("Select a page:", ["Planner 🗺️", "Flights ✈️", "Hotels 🏨"])

# Add visual divider
st.sidebar.markdown("---")

# Instructions section
st.sidebar.header("📖 Instructions")
st.sidebar.markdown("""
### How to use GetSetGo:

#### 🗺️ Planner
1. Enter your destination city/country
2. Choose number of days for your trip
3. Click 'Generate Itinerary'
4. Get a detailed day-by-day travel plan

#### ✈️ Flights
1. Select departure & arrival airports from dropdowns
2. Choose departure and return dates
3. Click 'Search Flights'
4. View available flights in both directions

#### 🏨 Hotels
1. Enter your destination city
2. Add any specific preferences (optional)
3. Click 'Find Hotels'
4. Browse hotels by star rating
""")


if groq_api_key and serp_api_key:
    if page == "Planner 🗺️":
        st.title("🗺️ Travel Planner")
        st.write("Plan your itinerary here.")
        researcher = Agent(
            name="Researcher",
            role="Searches for travel destinations, activities, and accommodations based on user preferences",
            model=Groq(id="llama-3.3-70b-versatile", api_key=groq_api_key),
            show_tool_calls=False,
            markdown=True,
            description=dedent(
                """\
                You are a world-class travel researcher. Given a travel destination and the number of days the user wants to travel for,
                generate a list of search terms for finding relevant travel activities and accommodations.
                Then search the web for each term, analyze the results, and return the 10 most relevant results.
                """
            ),
            instructions=[
                "Given a travel destination and the number of days the user wants to travel for, first generate a list of 3 search terms related to that destination and the number of days.",
                "For each search term, `search_google` and analyze the results.",
                "From the results of all searches, return the 10 most relevant results to the user's preferences.",
                "Remember: the quality of the results is important.",
            ],
            tools=[SerpApiTools(api_key=serp_api_key)],
            add_datetime_to_instructions=True,
        )
        planner = Agent(
            name="Planner",
            role="Generates a draft itinerary based on user preferences and research results",
            model=Groq(id="llama-3.3-70b-versatile", api_key=groq_api_key),
            show_tool_calls=False,
            markdown=True,
            description=dedent(
                """\
                You are a senior travel planner. Given a travel destination, the number of days the user wants to travel for, and a list of research results,
                your goal is to generate a draft itinerary that meets the user's needs and preferences.
                """
            ),
            instructions=[
                "Given a travel destination, the number of days the user wants to travel for, and a list of research results, generate a draft itinerary that includes suggested activities and accommodations.",
                "Ensure the itinerary is well-structured, informative, and engaging.",
                "Ensure you provide a nuanced and balanced itinerary, quoting facts where possible.",
                "Remember: the quality of the itinerary is important.",
                "Focus on clarity, coherence, and overall quality.",
                "Never make up facts or plagiarize. Always provide proper attribution.",
                "If a specific location type (beach, mountain, city, etc.) is provided, prioritize relevant attractions and activities.",
            ],
            add_datetime_to_instructions=True,
        )

        destination = st.text_input("Which place you want to visit?", placeholder="(e.g., Mumbai)")
        num_days = st.number_input("How many days do you want to travel for?", min_value=1, max_value=30, value=1)
        location_type=st.text_input("What type of location are you looking for?", placeholder="(e.g., beach, mountain, city)")

        if st.button("Generate Itinerary"):
            with st.spinner("Processing..."):
                # Get the response from the assistant
                prompt = f"{destination} for {num_days} days"
                if location_type:
                    prompt += f", focusing on {location_type} attractions and activities"
                
                response = planner.run(prompt, stream=False)
                itinerary_text = response.content
                
                # Add header with trip details
                header = f"""
# 🌟 Your {num_days}-Day Trip to {destination}
**Location Type:** {location_type if location_type else 'Not specified'}\n
---
"""
                st.markdown(header)
                st.write(itinerary_text)

    elif page == "Flights ✈️":
        # Load environment variables and initialize Gemini client
        api_key = st.secrets["GEMINI_API_KEY"]
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables.")
        client = genai.Client(api_key=api_key)

        def call_gemini_with_retry(prompt, max_retries=5, initial_delay=1, backoff_factor=2):
            model = "gemini-2.0-flash"
            contents = [types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)]
            )]
            
            config = types.GenerateContentConfig(
                temperature=1,
                top_p=0.95,
                top_k=40,
                max_output_tokens=8192,
                response_mime_type="text/plain",
            )

            delay = initial_delay
            for attempt in range(max_retries):
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=prompt,
                    )
                    return response.text
                except Exception as e:
                    if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                        if attempt < max_retries - 1:
                            wait_time = delay + random.uniform(0, 1)
                            st.warning(f"Rate limit exceeded. Waiting {wait_time:.2f} seconds... (Attempt {attempt + 1}/{max_retries})")
                            time.sleep(wait_time)
                            delay *= backoff_factor
                            continue
                    raise e
            
            raise Exception(f"Failed to call Gemini API after {max_retries} attempts")

        def process_flight_data_with_llm(flight_data, direction="outbound", max_options=5):
            # Debug the incoming data
            st.write(f"Processing {direction} flight data...")
            
            prompt = f"""
            For the {direction} journey, analyze the flight data and format ONLY the following details:
            
            For direct flights:
            ### Option [number] (Direct)
            - 🛩️ **Airline & Flight**: Extract from itineraries[0].segments[0].marketingCarrier.name and code + flightNumber
            - 🛫 **Departure**: Extract from itineraries[0].segments[0].departure.datetime and airport.code
            - 🛬 **Arrival**: Extract from itineraries[0].segments[0].arrival.datetime and airport.code
            - ⏱️ **Duration**: Extract from itineraries[0].segments[0].duration.minutes (format as hours and minutes)

            For connecting flights:
            ### Option [number] (Connecting)
            First Flight:
            - 🛩️ **Airline & Flight**: Extract first segment airline and flight number
            - 🛫 **Departure**: Extract first segment departure time and airport
            - 🛬 **Arrival**: Extract first segment arrival time and airport
            - ⏱️ **Duration**: Extract first segment duration

            Connection at [connection airport code]

            Second Flight:
            - 🛩️ **Airline & Flight**: Extract second segment airline and flight number
            - 🛫 **Departure**: Extract second segment departure time and airport
            - 🛬 **Arrival**: Extract second segment arrival time and airport
            - ⏱️ **Duration**: Extract second segment duration

            Total Journey Time: Calculate total duration including connection time

            Rules:
            1. Format times as "HH:MM, DD MMM"
            2. Format durations as "Xh Ym" (e.g., "2h 15m")
            3. Only show flights departing on the {str(depart_date) if direction == "outbound" else str(return_date)}
            4. Include airport codes in parentheses after times
            5. Show up to {max_options} options
            6. Sort by total duration, shortest first

            Flight data to analyze:
            {json.dumps(flight_data, indent=2)}

            Only respond with the formatted flight options. If no flights are found, respond with "No flights available for this route".
            """

            try:
                response = call_gemini_with_retry(prompt)
                if not response or "No flights available" in response:
                    return "No flights available for this route"
                return response
            except Exception as e:
                st.error(f"Error processing flights: {str(e)}")
                return "Error processing flight data"

        st.title("✈️ Air Navigator - Search Flights")

        def get_airports():
            try:
                return AIRPORTS
            except Exception as e:
                st.warning("Error loading airport data")
                return {}

        # Format airport options for dropdown
        def format_airport_options():
            return [f"{code} - {name}" for code, name in AIRPORTS.items()]

        # Extract airport code from selection
        def extract_airport_code(selection):
            return selection.split(' - ')[0]

        # Input fields
        airports = get_airports()
        formatted_airports = format_airport_options()

        col1, col2 = st.columns(2)
        with col1:
            from_airport = st.selectbox(
                "From Airport",
                options=[""] + sorted(formatted_airports, key=str.lower),
                key="from_airport",
                placeholder="Select departure airport"
            )
            from_id = extract_airport_code(from_airport) + ".AIRPORT" if from_airport else ""
            depart_date = st.date_input("Departure Date")
        with col2:
            to_airport = st.selectbox(
                "To Airport",
                options=[""] + sorted(formatted_airports, key=str.lower),
                key="to_airport",
                placeholder="Select arrival airport"
            )
            to_id = extract_airport_code(to_airport) + ".AIRPORT" if to_airport else ""
            return_date = st.date_input("Return Date")

        # Disable search button if airports are not selected
        search_disabled = not from_airport or not to_airport
        if search_disabled:
            st.warning("Please select both departure and arrival airports")

        if st.button("Search Flights", disabled=search_disabled):
            try:
                url = "https://booking-com15.p.rapidapi.com/api/v1/flights/searchFlights"
                
                headers = {
                    'x-rapidapi-key': "c7e0aa899dmsh615a27ae556567fp171c5djsnc377c451182b",
                    'x-rapidapi-host': "booking-com15.p.rapidapi.com"
                }

                querystring = {
                    "fromId": from_id,
                    "toId": to_id,
                    "departDate": str(depart_date),
                    "returnDate": str(return_date),
                    "pageNo": "1",
                    "adults": "1",
                    "children": "0",  # Changed to 0 for simpler testing
                    "sort": "BEST",
                    "cabinClass": "ECONOMY",
                    "currency_code": "USD"  # Changed to USD for better compatibility
                }

                st.info("Searching for flights...")
                response = requests.get(url, headers=headers, params=querystring)
                response.raise_for_status()
                
                data = response.json()
                
                if 'data' in data:
                    st.success("✈️ Flights found!")
                    
                    # Show raw response for debugging
                    #with st.expander("View API Response"):
                        #st.json(data)
                    
                    outbound_tab, return_tab = st.tabs(["🛫 Outbound Options", "🛬 Return Options"])
                    
                    with outbound_tab:
                        st.markdown("## 🛫 Outbound Flight Options")
                        if 'flightOffers' in data['data']:
                            outbound_flights = {
                                'flights': data['data']['flightOffers'][:5],  # Take first 5 flights
                                'direction': 'outbound'
                            }
                            outbound_response = process_flight_data_with_llm(outbound_flights, "outbound")
                            st.markdown(outbound_response)
                        else:
                            st.warning("No outbound flights found")
                        
                    with return_tab:
                        st.markdown("## 🛬 Return Flight Options")
                        if 'flightOffers' in data['data']:
                            return_flights = {
                                'flights': data['data']['flightOffers'][-5:],  # Take last 5 flights
                                'direction': 'return'
                            }
                            return_response = process_flight_data_with_llm(return_flights, "return")
                            st.markdown(return_response)
                        else:
                            st.warning("No return flights found")
                else:
                    st.warning("No flights found for the specified criteria.")
                    
            except requests.exceptions.RequestException as e:
                st.error(f"API Request Error: {str(e)}")
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                st.error(f"Error details: {str(e)}")

    elif page == "Hotels 🏨":
        st.title("🏨 Dream Stays - Find Hotels")

        

        # Initialize Gemini client
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        model_id = "gemini-2.0-flash"

        def get_hotel_recommendations(location, preferences):
            prompt = f"""Provide hotel suggestions in {location}.
            Consider these preferences: {preferences}

            List exactly 5 hotels for each category (mark them as specified below):
            • 5-star hotels (⭐⭐⭐⭐⭐)
            • 4-star hotels (⭐⭐⭐⭐)
            • 3-star hotels (⭐⭐⭐)

            For each hotel include:
            1. 💰 Price range per night (INR)
            2. 🛏️ Room types
            3. 📍 Location details
            4. ⭐ Rating
            5. 🏨 Key amenities
            6. 👥 Best suited for

            Format with clear headings and bullet points."""

            response = client.models.generate_content(
                model=model_id,
                contents=prompt,
                config=GenerateContentConfig(
                    response_modalities=["TEXT"],
                )
            )
            
            return response.candidates[0].content.parts[0].text


        # Top section for inputs
        st.markdown("""
        <style>
            .input-section { padding: 20px; margin-bottom: 20px; }
            .stButton button { 
                min-width: 200px; 
                margin-top: 0px;
                padding: 0.5rem 1rem;
            }
            div[data-testid="stHorizontalBlock"] {
                align-items: flex-end;
            }
        </style>
        """, unsafe_allow_html=True)

        with st.container():
            col1, col2 = st.columns(2)
            
            with col1:
                location = st.text_input("🌍 Location", placeholder="Enter city name (e.g., Mumbai)")
            with col2:
                preferences = st.text_input("✨ Preferences", placeholder="e.g., near beach, family-friendly")
            
            # Move button below the columns
            search = st.button("🔍 Find Hotels", use_container_width=True)

        # Divider
        st.markdown("---")

        # Results section
        if search:
            if location:
                with st.spinner("🔄 Finding best hotels..."):
                    try:
                        recommendations = get_hotel_recommendations(location, preferences)
                        st.markdown(f"### 🏨 Hotels in {location}")
                        st.markdown(recommendations)
                    except:
                        st.error("🚫 Unable to fetch hotel details")
            else:
                st.warning("🎯 Please enter a location")
