{
 "cells": [
  {
   "cell_type": "code",
   "execution_count": 17,
   "metadata": {},
   "outputs": [
    {
     "name": "stderr",
     "output_type": "stream",
     "text": [
      "usage: ipykernel_launcher.py [-h] [--min-dte MIN_DTE] [--max-dte MAX_DTE]\n",
      "                             [--lookback LOOKBACK] [--atm-percent ATM_PERCENT]\n",
      "                             ticker\n",
      "ipykernel_launcher.py: error: the following arguments are required: ticker\n"
     ]
    },
    {
     "ename": "SystemExit",
     "evalue": "2",
     "output_type": "error",
     "traceback": [
      "An exception has occurred, use %tb to see the full traceback.\n",
      "\u001b[1;31mSystemExit\u001b[0m\u001b[1;31m:\u001b[0m 2\n"
     ]
    }
   ],
   "source": [
    "import requests\n",
    "import datetime\n",
    "import statistics\n",
    "import os\n",
    "import argparse\n",
    "import math\n",
    "\n",
    "# --- Configuration ---\n",
    "OPTIONS_API_BASE_URL = \"https://eodhd.com/api/mp/unicornbay/options\"\n",
    "EQUITY_API_BASE_URL = \"https://eodhd.com/api\" \n",
    "\n",
    "# --- Get API Key (Recommended: Use environment variable) ---\n",
    "# Demo key from docs (ONLY WORKS FOR AAPL EXAMPLES - REPLACE WITH YOURS)\n",
    "API_TOKEN = \"67fb3d6f50c489.92544905\" \n",
    "\n",
    "# --- Helper Functions ---\n",
    "\n",
    "def get_eodhd_data(base_url, endpoint_path, params):\n",
    "    \"\"\"Fetches data from a specified EODHD API base URL.\"\"\"\n",
    "    if not API_TOKEN or API_TOKEN == 'YOUR_API_KEY':\n",
    "        raise ValueError(\"API Token not configured. Set EODHD_API_TOKEN environment variable or edit the script.\")\n",
    "        \n",
    "    url = f\"{base_url}/{endpoint_path}\"\n",
    "    params['api_token'] = API_TOKEN\n",
    "    params['fmt'] = 'json' # Ensure response is JSON\n",
    "    \n",
    "    response = None # Initialize response to None\n",
    "    try:\n",
    "        # print(f\"DEBUG: Calling URL: {url} with params: {params}\") # Uncomment for debugging API calls\n",
    "        response = requests.get(url, params=params)\n",
    "        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)\n",
    "        # Handle cases where EOD API might return list directly vs options API returning dict\n",
    "        data = response.json()\n",
    "        # print(f\"DEBUG: Received data type: {type(data)}\") # Debugging\n",
    "        return data\n",
    "    except requests.exceptions.RequestException as e:\n",
    "        print(f\"Error fetching data from EODHD API ({url}): {e}\")\n",
    "        if response is not None:\n",
    "            print(f\"Response status code: {response.status_code}\")\n",
    "            print(f\"Response text: {response.text[:500]}...\") # Print first 500 chars\n",
    "        return None\n",
    "    except ValueError as e: # Catches JSONDecodeError if response isn't JSON\n",
    "        print(f\"Error decoding JSON response from {url}: {e}\")\n",
    "        if response is not None:\n",
    "            print(f\"Response text: {response.text[:500]}...\")\n",
    "        return None\n",
    "\n",
    "def get_stock_price(ticker):\n",
    "    \"\"\"Gets the latest closing price for the ticker.\"\"\"\n",
    "    # Use the EOD endpoint for the equity\n",
    "    # Append \".US\" exchange code - adjust if needed for other exchanges\n",
    "    endpoint = f\"eod/{ticker.upper()}.US\" \n",
    "    params = {'order': 'd', 'limit': 1} # Get descending order, limit 1 (latest day)\n",
    "    \n",
    "    data = get_eodhd_data(EQUITY_API_BASE_URL, endpoint, params)\n",
    "    \n",
    "    if data and isinstance(data, list) and len(data) > 0:\n",
    "        # EOD endpoint often returns a list of daily bars\n",
    "        latest_data = data[0]\n",
    "        if 'adjusted_close' in latest_data:\n",
    "            return latest_data['adjusted_close']\n",
    "        elif 'close' in latest_data:\n",
    "             return latest_data['close'] # Fallback to close if adjusted isn't there\n",
    "    \n",
    "    print(f\"Warning: Could not retrieve latest stock price for {ticker}.\")\n",
    "    return None\n",
    "\n",
    "def calculate_dte(exp_date_str):\n",
    "    \"\"\"Calculates Days To Expiration from a YYYY-MM-DD string.\"\"\"\n",
    "    try:\n",
    "        exp_date = datetime.datetime.strptime(exp_date_str, '%Y-%m-%d').date()\n",
    "        today = datetime.date.today()\n",
    "        dte = (exp_date - today).days\n",
    "        return dte\n",
    "    except (ValueError, TypeError):\n",
    "        return None\n",
    "\n",
    "# --- Main Calculation Logic ---\n",
    "\n",
    "def calculate_iv_rank(ticker, min_dte=25, max_dte=30, lookback_days=365, atm_percent=10):\n",
    "    \"\"\"Calculates IV Rank using ATM options for current IV and history basis.\"\"\"\n",
    "    \n",
    "    print(f\"\\nCalculating IV Rank for {ticker} ({min_dte}-{max_dte} DTE, ATM +/- {atm_percent}%, {lookback_days}-day lookback)...\")\n",
    "\n",
    "    # --- Get Current Stock Price ---\n",
    "    print(\"Step 1: Fetching current stock price...\")\n",
    "    stock_price = get_stock_price(ticker)\n",
    "    if stock_price is None:\n",
    "        print(f\"Error: Cannot proceed without stock price for {ticker}.\")\n",
    "        return None\n",
    "    print(f\"   Latest Stock Price ({ticker}): {stock_price:.2f}\")\n",
    "\n",
    "    # --- Find Current Options in DTE range ---\n",
    "    print(f\"\\nStep 2: Finding all options expiring in {min_dte}-{max_dte} days...\")\n",
    "    today = datetime.date.today()\n",
    "    target_exp_date_start = today + datetime.timedelta(days=min_dte)\n",
    "    target_exp_date_end = today + datetime.timedelta(days=max_dte)\n",
    "    \n",
    "    contracts_params = {\n",
    "        'filter[underlying_symbol]': ticker,\n",
    "        'filter[exp_date_from]': target_exp_date_start.strftime('%Y-%m-%d'),\n",
    "        'filter[exp_date_to]': target_exp_date_end.strftime('%Y-%m-%d'),\n",
    "        'fields[options-contracts]': 'contract,exp_date,volatility,strike,type' \n",
    "    }\n",
    "    \n",
    "    contracts_data = get_eodhd_data(OPTIONS_API_BASE_URL, 'contracts', contracts_params)\n",
    "\n",
    "    if not contracts_data or 'data' not in contracts_data or not contracts_data['data']:\n",
    "        print(f\"Error: No options data found for {ticker} in the {min_dte}-{max_dte} DTE range.\")\n",
    "        return None\n",
    "\n",
    "    # --- Filter for ATM Contracts & Calculate Current ATM IV ---\n",
    "    print(f\"\\nStep 3: Filtering for ATM (+/- {atm_percent}%) contracts and calculating current average ATM IV...\")\n",
    "    atm_ivs = []\n",
    "    atm_contracts = []\n",
    "    min_strike_diff = float('inf')\n",
    "    closest_atm_contract = None\n",
    "\n",
    "    for contract in contracts_data['data']:\n",
    "        attributes = contract.get('attributes', {})\n",
    "        exp_date_str = attributes.get('exp_date')\n",
    "        volatility = attributes.get('volatility')\n",
    "        strike = attributes.get('strike')\n",
    "        contract_id = attributes.get('contract')\n",
    "\n",
    "        if exp_date_str and contract_id and strike is not None:\n",
    "            dte = calculate_dte(exp_date_str)\n",
    "            # Check DTE range\n",
    "            if dte is not None and min_dte <= dte <= max_dte:\n",
    "                try:\n",
    "                    strike_float = float(strike)\n",
    "                    # Check ATM range\n",
    "                    strike_diff = abs(strike_float - stock_price)\n",
    "                    if strike_diff <= stock_price * (atm_percent / 100.0):\n",
    "                        if volatility is not None:\n",
    "                            try:\n",
    "                                iv = float(volatility)\n",
    "                                if iv > 0: # Basic sanity check for positive IV\n",
    "                                     atm_ivs.append(iv)\n",
    "                                     atm_contracts.append(contract)\n",
    "                                     # Track the contract closest to the stock price\n",
    "                                     if strike_diff < min_strike_diff:\n",
    "                                         min_strike_diff = strike_diff\n",
    "                                         closest_atm_contract = contract\n",
    "                                # else: \n",
    "                                #      print(f\"DEBUG: Skipping ATM contract {contract_id} due to non-positive volatility: {iv}\")\n",
    "                            except (ValueError, TypeError):\n",
    "                                pass # Silently skip contracts with invalid volatility\n",
    "                        # else:\n",
    "                            # print(f\"DEBUG: Skipping ATM contract {contract_id} due to missing volatility.\")\n",
    "                except (ValueError, TypeError):\n",
    "                     pass # Silently skip contracts with invalid strike\n",
    "\n",
    "    if not atm_ivs:\n",
    "        print(f\"Error: No valid ATM options found for {ticker} within +/- {atm_percent}% in the {min_dte}-{max_dte} DTE range.\")\n",
    "        return None\n",
    "        \n",
    "    if not closest_atm_contract:\n",
    "        print(f\"Error: Could not identify a closest ATM contract for historical lookup.\")\n",
    "        return None\n",
    "\n",
    "    current_avg_atm_iv = statistics.mean(atm_ivs)\n",
    "    print(f\"   Found {len(atm_ivs)} ATM options with valid IV in DTE range.\")\n",
    "    print(f\"   Current Average ATM IV ({min_dte}-{max_dte} DTE): {current_avg_atm_iv:.4f}\")\n",
    "\n",
    "\n",
    "    # --- 4. Get Historical IV for the Representative ATM Contract ---\n",
    "    print(\"\\nStep 4: Fetching historical IV data (using closest ATM contract)...\")\n",
    "    \n",
    "    representative_contract_attrs = closest_atm_contract['attributes']\n",
    "    rep_contract_id = representative_contract_attrs['contract']\n",
    "    print(f\"   Using closest ATM contract {rep_contract_id} (Exp: {representative_contract_attrs['exp_date']}, Strike: {representative_contract_attrs['strike']}, Type: {representative_contract_attrs['type']}) for history.\")\n",
    "\n",
    "    hist_start_date = today - datetime.timedelta(days=lookback_days)\n",
    "    hist_end_date = today # Go up to yesterday/today depending on API data availability\n",
    "\n",
    "    eod_params = {\n",
    "        'filter[contract]': rep_contract_id,\n",
    "        'from': hist_start_date.strftime('%Y-%m-%d'),\n",
    "        'to': hist_end_date.strftime('%Y-%m-%d'),\n",
    "        'fields[options-eod]': 'date,volatility' # Request only date and volatility\n",
    "    }\n",
    "\n",
    "    historical_data = get_eodhd_data(OPTIONS_API_BASE_URL, 'eod', eod_params)\n",
    "\n",
    "    if not historical_data or 'data' not in historical_data or not historical_data['data']:\n",
    "        # Attempting to proceed even if historical data is sparse or missing, will calculate rank based on what's found.\n",
    "        print(f\"Warning: No historical EOD data found for representative contract {rep_contract_id} in the last {lookback_days} days. IV Rank may be inaccurate.\")\n",
    "        historical_ivs = []\n",
    "    else:\n",
    "         historical_ivs = []\n",
    "         for day_data in historical_data['data']:\n",
    "             attributes = day_data.get('attributes', {})\n",
    "             volatility = attributes.get('volatility')\n",
    "             if volatility is not None:\n",
    "                 try:\n",
    "                     iv = float(volatility)\n",
    "                     if iv > 0: # Only consider valid positive IVs\n",
    "                         historical_ivs.append(iv)\n",
    "                 except (ValueError, TypeError):\n",
    "                     pass # Ignore invalid historical values silently\n",
    "    \n",
    "    # --- 5. Determine Historical High/Low IV ---\n",
    "    print(\"\\nStep 5: Determining historical IV range...\")\n",
    "    if not historical_ivs:\n",
    "        print(\"   No valid historical volatility values found. Cannot determine range or rank.\")\n",
    "        hist_low_iv = None\n",
    "        hist_high_iv = None\n",
    "        iv_rank = None\n",
    "    else:\n",
    "        if len(historical_ivs) < lookback_days * 0.1: # Warn if data seems very sparse\n",
    "            print(f\"   Warning: Found only {len(historical_ivs)} valid historical IV data points in the last {lookback_days} days for {rep_contract_id}.\")\n",
    "        hist_low_iv = min(historical_ivs)\n",
    "        hist_high_iv = max(historical_ivs)\n",
    "        print(f\"   Historical IV Low ({lookback_days}-day): {hist_low_iv:.4f}\")\n",
    "        print(f\"   Historical IV High ({lookback_days}-day): {hist_high_iv:.4f}\")\n",
    "\n",
    "        # --- 6. Calculate IV Rank ---\n",
    "        print(\"\\nStep 6: Calculating IV Rank...\")\n",
    "        iv_range = hist_high_iv - hist_low_iv\n",
    "\n",
    "        if iv_range == 0:\n",
    "            # Avoid division by zero.\n",
    "            iv_rank = 50.0 if current_avg_atm_iv == hist_low_iv else (0.0 if current_avg_atm_iv < hist_low_iv else 100.0)\n",
    "            print(f\"   Warning: Historical IV range is zero. Setting IV Rank based on current vs historical level ({iv_rank}).\")\n",
    "        else:\n",
    "            iv_rank = ((current_avg_atm_iv - hist_low_iv) / iv_range) * 100\n",
    "            iv_rank = max(0.0, min(100.0, iv_rank)) # Clamp between 0 and 100\n",
    "\n",
    "    # --- Output Result ---\n",
    "    print(f\"\\n--- Result for {ticker} ---\")\n",
    "    print(f\"Current Stock Price:      {stock_price:.2f}\")\n",
    "    print(f\"Current Avg ATM IV ({min_dte}-{max_dte} DTE): {current_avg_atm_iv:.4f}\")\n",
    "    if hist_low_iv is not None and hist_high_iv is not None:\n",
    "        print(f\"{lookback_days}-Day IV Low (ATM basis): {hist_low_iv:.4f}\")\n",
    "        print(f\"{lookback_days}-Day IV High (ATM basis):{hist_high_iv:.4f}\")\n",
    "    else:\n",
    "        print(f\"{lookback_days}-Day IV Low (ATM basis): N/A\")\n",
    "        print(f\"{lookback_days}-Day IV High (ATM basis):N/A\")\n",
    "        \n",
    "    if iv_rank is not None:\n",
    "        print(f\"IV Rank:                  {iv_rank:.2f}\")\n",
    "    else:\n",
    "        print(f\"IV Rank:                  N/A (Insufficient historical data)\")\n",
    "    print(\"------------------------\")\n",
    "    \n",
    "    return {\n",
    "        \"ticker\": ticker,\n",
    "        \"stock_price\": stock_price,\n",
    "        \"current_avg_atm_iv\": current_avg_atm_iv,\n",
    "        \"hist_low_iv\": hist_low_iv,\n",
    "        \"hist_high_iv\": hist_high_iv,\n",
    "        \"iv_rank\": iv_rank\n",
    "    }\n",
    "\n",
    "# --- Script Execution ---\n",
    "if __name__ == \"__main__\":\n",
    "    parser = argparse.ArgumentParser(description=\"Calculate IV Rank for a stock using EODHD Options API, focusing on ATM contracts.\")\n",
    "    parser.add_argument(\"ticker\", help=\"Stock ticker symbol (e.g., AAPL). Assumes .US exchange.\")\n",
    "    parser.add_argument(\"--min-dte\", type=int, default=25, help=\"Minimum Days To Expiration (default: 25)\")\n",
    "    parser.add_argument(\"--max-dte\", type=int, default=30, help=\"Maximum Days To Expiration (default: 30)\")\n",
    "    parser.add_argument(\"--lookback\", type=int, default=365, help=\"Lookback period in days for historical IV (default: 365)\")\n",
    "    parser.add_argument(\"--atm-percent\", type=int, default=10, help=\"Percentage range (+/-) around stock price to consider ATM (default: 10)\")\n",
    "    \n",
    "    args = parser.parse_args()\n",
    "\n",
    "    if API_TOKEN == 'YOUR_API_KEY' or not API_TOKEN:\n",
    "         print(\"Error: Please set the EODHD_API_TOKEN environment variable or replace 'YOUR_API_KEY' in the script.\")\n",
    "    else:\n",
    "        calculate_iv_rank(args.ticker.upper(), args.min_dte, args.max_dte, args.lookback, args.atm_percent)"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "Python 3",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.12.6"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 2
}
