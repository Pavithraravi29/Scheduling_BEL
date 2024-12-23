import streamlit as st
import requests
import pandas as pd
import altair as alt

# Set page title and header
st.set_page_config(page_title="Production Schedule", page_icon=":factory:", layout="wide")
st.title("Production Schedule")

# Make a request to the scheduling endpoint
try:
    response = requests.get("http://172.18.7.88:2727/schedule/")
    response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
    data = response.json()
except requests.exceptions.RequestException as e:
    st.error(f"Error fetching data from the scheduling endpoint: {e}")
    st.warning("Please check the server connection and try again.")
    st.stop()
# Extract the scheduled operations data
operations_data = data["scheduled_operations"]

if not operations_data:
    st.warning("No scheduled operations found.")
else:
    # Convert the operations data to a DataFrame
    df = pd.DataFrame(operations_data)
    df["start_time"] = pd.to_datetime(df["start_time"], format="mixed")
    df["end_time"] = pd.to_datetime(df["end_time"], format="mixed")
    
    # Display overall production metrics
    st.header("Overall Production Metrics")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Overall End Time", data["overall_end_time"])
    with col2:
        st.metric("Overall Time (minutes)", data["overall_time"])
    
    # Display the operations schedule as a Gantt chart
    st.header("Operations Schedule")
    chart = alt.Chart(df).mark_bar().encode(
        x='start_time:T',
        x2='end_time:T',
        y='machine:N',
        color='component:N',
        tooltip=['component', 'description', 'quantity', 'start_time', 'end_time']
    ).interactive()
    st.altair_chart(chart, use_container_width=True)
    
    # Display daily production counts
    st.header("Daily Production")
    daily_production = data["daily_production"]
    daily_production_df = pd.DataFrame.from_dict(daily_production, orient="index")
    daily_production_df = daily_production_df.stack().reset_index()
    daily_production_df.columns = ["component", "date", "quantity"]
    daily_production_df["date"] = pd.to_datetime(daily_production_df["date"])
    
    daily_chart = alt.Chart(daily_production_df).mark_bar().encode(
        x='date:T',
        y='quantity:Q',
        color='component:N',
        tooltip=['component', 'date', 'quantity']
    ).interactive()
    st.altair_chart(daily_chart, use_container_width=True)
    
    # Display component status
    st.header("Component Status")
    component_status = data["component_status"]
    component_status_df = pd.DataFrame.from_dict(component_status, orient="index")
    st.table(component_status_df)