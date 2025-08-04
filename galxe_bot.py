import asyncio
import time
import os
import json
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
import requests
import mysql.connector
import discord
from discord.ext import commands
from db_config_galxe import config as db_config_galxe
from dotenv import load_dotenv

# ======================== CONFIG =========================

load_dotenv()

API_URL = os.getenv("GALXE_API_URL")
ACCESS_TOKEN = os.getenv("GALXE_ACCESS_TOKEN")
SPACE_ID = os.getenv("SPACE_ID")
SPECIFIC_CAMPAIGN_ID = None
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# ======================== DATABASE =======================

def init_database():
    try:
        conn = mysql.connector.connect(**db_config_galxe)
        conn.autocommit = True
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS genome (
                    galxeID VARCHAR(255) PRIMARY KEY,
                    inserted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        print("✅ Connected to MySQL database")
        return conn
    except mysql.connector.Error as e:
        print(f"❌ Error connecting to MySQL database: {e}")
        return None

# ===================== SETUP CLIENT ======================

transport = RequestsHTTPTransport(
    url=API_URL,
    headers={"access-token": ACCESS_TOKEN},
    verify=True,
    retries=3,
)
client = Client(transport=transport, fetch_schema_from_transport=False)

# ===================== DISCORD BOT ======================

intents = discord.Intents.default()
intents.message_content = True

class CustomBot(commands.Bot):
    async def connect(self, reconnect=True):
        while True:
            try:
                await super().connect(reconnect=reconnect)
                break
            except asyncio.TimeoutError:
                print("❌ WebSocket connection timed out. Retrying in 10 seconds...")
                await asyncio.sleep(10)
            except Exception as e:
                print(f"❌ Connection error: {str(e)}. Retrying in 10 seconds...")
                await asyncio.sleep(10)

bot = CustomBot(command_prefix="!", intents=intents)
poll_task = None  # Global variable to track the polling task

@bot.event
async def on_ready():
    global poll_task
    print(f"✅ Discord bot logged in as {bot.user}")
    if poll_task is None or poll_task.done():
        print("Starting Galxe polling task")
        poll_task = bot.loop.create_task(poll_galxe())
    else:
        print("Galxe polling task already running")

@bot.event
async def on_close():
    global poll_task
    if poll_task and not poll_task.done():
        poll_task.cancel()
        try:
            await poll_task
        except asyncio.CancelledError:
            print("✅ Polling task cancelled")
    print("✅ Bot shut down")

# ===================== GRAPHQL QUERIES ===================

space_campaigns_query = gql("""
query GetCampaigns($id: Int!, $input: ListCampaignInput!) {
  space(id: $id) {
    id
    name
    campaigns(input: $input) {
      edges {
        node {
          id
          name
          status
        }
        cursor
      }
      pageInfo {
        hasNextPage
        endCursor
      }
    }
  }
}
""")

campaign_details_query = gql("""
query GetCampaignDetails($id: ID!) {
  campaign(id: $id) {
    id
    name
    status
    tags
  }
}
""")

test_connection_query = """
query TestConnection($id: Int!) {
  space(id: $id) {
    id
    name
  }
}
"""

# ===================== FUNCTIONS =========================

async def get_space_campaigns(space_id, conn):
    """
    Fetch all campaigns for a space by its ID, handling pagination.
    """
    try:
        all_campaigns = []
        has_next_page = True
        end_cursor = None

        while has_next_page:
            variables = {
                "id": space_id,
                "input": {
                    "first": 50,
                    "after": end_cursor
                }
            }
            result = client.execute(space_campaigns_query, variable_values=variables)
            space = result.get("space", {})
            if not space:
                print(f"No space found for ID: {space_id}")
                return None

            campaigns_raw = space.get("campaigns", {})
            edges = campaigns_raw.get("edges", [])
            campaigns = [edge["node"] for edge in edges]
            all_campaigns.extend(campaigns)

            page_info = campaigns_raw.get("pageInfo", {})
            has_next_page = page_info.get("hasNextPage", False)
            end_cursor = page_info.get("endCursor", None)

        if not all_campaigns:
            print("No campaigns found.")
            return None

        print(f"\n📦 Space: {space.get('name')} (ID: {space.get('id')})")
        for campaign in all_campaigns:
            campaign_id = campaign.get("id")
            if not getQuest(campaign_id, conn):
                addQuestToDB(campaign_id, conn)
                print(f"New Quest found: ➤ ID: {campaign_id}, Name: {campaign.get('name')}, Status: {campaign.get('status')}")
                await newQuest(campaign.get("name"), campaign_id)
        
        return all_campaigns

    except Exception as e:
        print(f"❌ Error fetching campaigns: {str(e)}")
        return None

def get_campaign_details(campaign_id, campaign_name):
    """
    Fetch details for a given campaign.
    """
    try:
        result = client.execute(campaign_details_query, variable_values={"id": campaign_id})
        campaign = result.get("campaign", {})
        if not campaign:
            print(f"No campaign found for ID: {campaign_id}")
            return None

        print(f"\n📍 Campaign: {campaign.get('name')} (ID: {campaign.get('id')})")
        status = campaign.get("status")
        tags = campaign.get("tags")

        if status:
            print(f"  Status: {status}")
        else:
            print("  No status found.")

        if tags:
            print(f"  Tags: {tags}")
        else:
            print("  No tags found.")
        return campaign

    except Exception as e:
        print(f"❌ Error fetching campaign details for {campaign_name}: {str(e)}")
        return None

# ======================= DB FUNCTIONS =====================

def addQuestToDB(galxeID, conn):
    """
    Insert a Galxe campaign ID into the genome table.
    """
    cursor = None
    try:
        cursor = conn.cursor()
        insert_sql = "INSERT INTO genome (galxeID) VALUES (%s)"
        cursor.execute(insert_sql, (galxeID,))
        print(f"✅ Inserted campaign ID: {galxeID} into genome table.")
    except mysql.connector.Error as e:
        print(f"❌ Error inserting campaign ID {galxeID}: {str(e)}")
    finally:
        if cursor:
            cursor.close()

def getQuest(galxeID, conn):
    """
    Check if a Galxe campaign ID exists in the genome table.
    """
    cursor = None
    try:
        cursor = conn.cursor()
        query = "SELECT galxeID FROM genome WHERE galxeID = %s"
        cursor.execute(query, (galxeID,))
        result = cursor.fetchone()
        return bool(result)
    except mysql.connector.Error as e:
        print(f"❌ Error checking campaign ID {galxeID}: {str(e)}")
        return False
    finally:
        if cursor:
            cursor.close()

# ======================= DISCORD NOTIFICATIONS ===========

async def newQuest(questName, questID):
    """
    Send a Discord notification for a new Galxe quest.
    """
    channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if channel is None:
        print(f"❌ Channel ID {DISCORD_CHANNEL_ID} not found.")
        return

    embed = discord.Embed(description="New Galxe quest is live:")
    embed.colour = discord.Colour.green()
    embed.add_field(
        name=questName,
        value=f"[Quest Link](https://app.galxe.com/quest/Genome/{questID})",
        inline=False
    )
    try:
        await channel.send(content="<@&1363487316600946818>", embed=embed)
        print(f"✅ Sent Discord notification for quest: {questName} (ID: {questID})")
    except discord.DiscordException as e:
        print(f"❌ Error sending Discord notification: {str(e)}")

# ======================= POLLING TASK ====================

async def poll_galxe():
    """
    Periodically poll the Galxe API for new campaigns.
    """
    conn = init_database()
    if not conn:
        print("❌ Aborting due to database initialization failure.")
        return

    last_poll_time = time.time()
    try:
        while True:
            current_time = time.time()
            time_since_last_poll = current_time - last_poll_time
            print(f"📅 Polling at {time.strftime('%Y-%m-%d %H:%M:%S')}, "
                  f"time since last poll: {time_since_last_poll:.2f}s, "
                  f"active tasks: {len(asyncio.all_tasks())}")
            last_poll_time = current_time

            try:
                if not ACCESS_TOKEN or ACCESS_TOKEN == "your_access_token_here":
                    print("⚠️ Please provide a valid Galxe access token.")
                    break

                print(f"🌐 Testing connection to Galxe API: {API_URL}")
                try:
                    # Test API with a proper GraphQL POST request
                    payload = {
                        "query": test_connection_query,
                        "variables": {"id": SPACE_ID}
                    }
                    response = requests.post(
                        API_URL,
                        headers={"access-token": ACCESS_TOKEN, "Content-Type": "application/json"},
                        json=payload,
                        timeout=5
                    )
                    print(f"✅ API test response: {response.status_code}")
                    if response.status_code != 200:
                        print(f"❌ API error details: {response.text}")
                    else:
                        try:
                            response_data = response.json()
                            if "data" in response_data and response_data["data"].get("space"):
                                print(f"✅ API test successful: Space {response_data['data']['space']['name']}")
                            else:
                                print(f"❌ API test failed: No space data in response")
                        except json.JSONDecodeError:
                            print(f"❌ API test failed: Invalid JSON response: {response.text}")
                except requests.exceptions.RequestException as e:
                    print(f"❌ Failed to connect to API: {str(e)}")
                    await asyncio.sleep(15)
                    continue

                if SPECIFIC_CAMPAIGN_ID:
                    print(f"\n🔎 Fetching details for campaign ID: {SPECIFIC_CAMPAIGN_ID}")
                    campaign = get_campaign_details(SPECIFIC_CAMPAIGN_ID, "Specific Campaign")
                    if campaign and not getQuest(SPECIFIC_CAMPAIGN_ID, conn):
                        addQuestToDB(SPECIFIC_CAMPAIGN_ID, conn)
                        await newQuest(campaign.get("name"), SPECIFIC_CAMPAIGN_ID)
                else:
                    print(f"\n🔍 Fetching campaigns for space ID: {SPACE_ID}")
                    await get_space_campaigns(SPACE_ID, conn)

                await asyncio.sleep(15)  # Poll every 15 seconds
            except asyncio.CancelledError:
                print("✅ Polling task cancelled")
                raise
            except Exception as e:
                print(f"❌ Polling error: {str(e)}")
                await asyncio.sleep(15)  # Continue polling after error
    finally:
        if conn.is_connected():
            conn.close()
            print("✅ Database connection closed.")

# ======================= RUN =============================

if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("❌ DISCORD_BOT_TOKEN not set. Please set it in the environment variables.")
    else:
        bot.run(DISCORD_BOT_TOKEN)