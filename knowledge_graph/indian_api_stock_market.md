---
title: "How to Use the Indian Stock Exchange API"
description: "A comprehensive guide to accessing real-time and historical Indian stock market data."
publisher: "indianapi.in"
lang: "en"
url: "https://indianapi.in/documentation/indian-stock-market"
date: "2026-07-31T17:08:59.000Z"
word_count: 3737
reading_time: "15 min read"
---

## Table of Contents

- [Indian Stock Exchange API Documentation](#indian-stock-exchange-api-documentation)
- [Endpoints](#endpoints)
  - [1. Get Company Data by Name](#1-get-company-data-by-name)
  - [Sample Request](#sample-request)
  - [Sample Response](#sample-response)
  - [Detailed Description of Structured Data](#detailed-description-of-structured-data)
  - [2. Industry Search](#2-industry-search)
  - [3. Mutual Fund Search](#3-mutual-fund-search)
  - [4. Trending](#4-trending)
- [Trending Stocks API](#trending-stocks-api)
  - [5. Fetch 52 Week High Low Data](#5-fetch-52-week-high-low-data)
  - [6. NSE Most Active](#6-nse-most-active)
  - [7. BSE Most Active](#7-bse-most-active)
  - [8. Mutual Funds](#8-mutual-funds)
  - [9. Price Shockers](#9-price-shockers)
  - [10. Commodity Futures Data API](#10-commodity-futures-data-api)
  - [Endpoint: /commodities](#endpoint-commodities)
    - [11. Analyst Recommendations](#11-analyst-recommendations)
    - [HTTP Request](#http-request)
    - [URL Parameters](#url-parameters)
    - [Success Response](#success-response)
    - [Error Responses](#error-responses)
    - [Recommendations Key](#recommendations-key)
    - [Recommendation Snapshots](#recommendation-snapshots)
    - [Example Response](#example-response)
  - [12. Stock Forecasts](#12-stock-forecasts)
    - [Endpoint: /stock_forecasts](#endpoint-stock_forecasts)
  - [Classes and Enums](#classes-and-enums)
    - [PeriodType](#periodtype)
    - [DataType](#datatype)
    - [DataAge](#dataage)
    - [MeasureCode](#measurecode)
  - [13. Historical Data](#13-historical-data)
  - [14. Historical Stats](#14-historical-stats)
  - [Company](#company)
  - [Services](#services)
  - [Legal](#legal)

---

[Open in ChatGPTOpen in AI](https://chatgpt.com/?q=Read+https://indianapi.in/docs/indian-stock-market.md)

## Indian Stock Exchange API Documentation

Welcome to the Indian Stock Exchange API! This API provides real-time stock market data. Below, you will find detailed descriptions of the available endpoints, their methods, required parameters, and usage examples.

## Endpoints

---

### 1. Get Company Data by Name

- **Endpoint:** `/stock`
  - **Method:** GET
  - **Description:** Retrieve detailed financial data for a specific company using its name. The API supports full names, shortened names and common name of the stock.
  - **Parameters:**
    - `name` (required, string): The name, shortened name, or any search term livemint allows.

### Sample Request

```
GET /stock?name=Reliance
```

### Sample Response

```json
{
  "tickerId": "RELIANCE",
  "companyName": "Reliance Industries Limited",
  "industry": "Conglomerate",
  "companyProfile": {
    // ... detailed company profile data
  },
  "currentPrice": {
    "BSE": 2200.5,
    "NSE": 2195.75
  },
  "stockTechnicalData": {
    // ... technical data
  },
  "percentChange": 1.25,
  "yearHigh": 2400.0,
  "yearLow": 1800.0,
  "financials": {
    // ... financial data
  },
  "keyMetrics": {
    // ... key metrics
  },
  "futureExpiryDates": [
    "2024-06-28",
    "2024-07-26"
    // ... more dates
  ],
  "futureOverviewData": {
    // ... future overview data
  },
  "initialStockFinancialData": {
    // ... initial financial data
  },
  "analystView": {
    // ... analyst views
  },
  "recosBar": {
    // ... recommendations bar data
  },
  "riskMeter": {
    // ... risk meter data
  },
  "shareholding": {
    // ... shareholding data
  },
  "stockCorporateActionData": {
    // ... corporate action data
  },
  "stockDetailsReusableData": {
    // ... reusable stock details data
  },
  "recentNews": [
    // ... news articles
  ]
}
```

### Detailed Description of Structured Data

- **tickerId**: The unique identifier for the stock (e.g., "RELIANCE").
- **companyName**: The full name of the company.
- **industry**: The industry in which the company operates.
- **companyProfile**: Detailed information about the company.
- **currentPrice**: Current stock prices for BSE and NSE.
  - **BSE**: Current price on BSE.
  - **NSE**: Current price on NSE.
- **stockTechnicalData**: Technical analysis data of the stock.
- **percentChange**: Percentage change in stock price.
- **yearHigh**: Highest price of the stock in the past year.
- **yearLow**: Lowest price of the stock in the past year.
- **financials**: Financial statements and data of the company.
- **keyMetrics**: Key financial ratios and metrics.
- **futureExpiryDates**: Dates of future contract expiries.
- **futureOverviewData**: Overview data of futures contracts.
- **initialStockFinancialData**: Initial financial data of the stock.
- **analystView**: Analyst recommendations and views.
- **recosBar**: Data showing analyst recommendations.
- **riskMeter**: Risk assessment data.
- **shareholding**: Shareholding patterns.
- **stockCorporateActionData**: Information on corporate actions.
- **stockDetailsReusableData**: Reusable data details for the stock.
- **recentNews**: Recent news articles related to the company.

---

### 2. Industry Search

**Endpoint**: `GET /industry_search`

**Description**: This endpoint allows you to search for companies within a specific industry.

**Parameters**:

- `query` (string, required): The search term to query the industry.

**Response**:

```json
[
  {
    "id": "S0003051",
    "commonName": "Tata Consultancy Services",
    "mgIndustry": "Software & Programming",
    "mgSector": "Technology",
    "stockType": "Equity",
    "exchangeCodeBse": "532540",
    "exchangeCodeNsi": "TCS",
    "bseRic": "TCS.BO",
    "nseRic": "TCS.NS",
    "activeStockTrends": {
      "shortTermTrends": "Bearish",
      "longTermTrends": "Moderately Bearish",
      "overallRating": "Moderately Bearish"
    }
  },
  {
    "id": "S0003022",
    "commonName": "Tata Motors",
    "mgIndustry": "Auto & Truck Manufacturers",
    "mgSector": "Consumer Cyclical",
    "stockType": "Equity",
    "exchangeCodeBse": "500570",
    "exchangeCodeNsi": "TATAMOTORS",
    "bseRic": "TAMO.BO",
    "nseRic": "TAMO.NS",
    "activeStockTrends": {
      "shortTermTrends": "Moderately Bearish",
      "longTermTrends": "Bullish",
      "overallRating": "Bullish"
    }
  },
  {
    "id": "S0003297",
    "commonName": "Tata Motors DVR",
    "mgIndustry": "Auto & Truck Manufacturers",
    "mgSector": "Consumer Cyclical",
    "stockType": "Equity",
    "exchangeCodeBse": "570001",
    "exchangeCodeNsi": "TATAMTRDVR",
    "bseRic": "TAMdv.BO",
    "nseRic": "TAMdv.NS",
    "activeStockTrends": {
      "shortTermTrends": "Bearish",
      "longTermTrends": "Bullish",
      "overallRating": "Neutral"
    }
  },
  ...
]
```

### 3. Mutual Fund Search

**Endpoint**: `GET /mutual_fund_search`

**Description**: This endpoint allows you to search for mutual funds.

**Parameters**:

- `query` (string, required): The search term to query the mutual funds.

**Response**:

```json
[
  {
    "id": "MF000063",
    "schemeName": "Nippon India Equity Savings Bonus",
    "isin": "INF204KA1W02",
    "schemeType": "Open Ended Investment Company",
    "categoryId": "MFCAT002"
  },
  {
    "id": "MF000021",
    "schemeName": "Nippon India ELSS Tax Saver Fund Direct Plan Payout Income Dist cum Cap Wdrl",
    "isin": "INF204K01L30",
    "schemeType": "Open Ended Investment Company",
    "categoryId": "MFCAT003"
  },
  {
    "id": "MF000015",
    "schemeName": "Nippon India Vision Fund Direct Plan Payout Inc Dist cum Cap Wdrl",
    "isin": "INF204K01F04",
    "schemeType": "Open Ended Investment Company",
    "categoryId": "MFCAT003"
  },
  ...
]
```

### 4. Trending

## Trending Stocks API

This API provides a snapshot of the top gaining and losing stocks at the current moment, giving you valuable insights into market trends and potential trading opportunities.

**Endpoint:** `/trending`

**Method:** `GET`

**Response Format:** `JSON`

**Data Returned:**

```json
{
  "trending_stocks": {
    "top_gainers": [
      {
        "ticker_id": "string",
        "company_name": "string",
        "price": "string",
        "percent_change": "string",
        "net_change": "string",
        "bid": "string",
        "ask": "string",
        "high": "string",
        "low": "string",
        "open": "string",
        "low_circuit_limit": "string",
        "up_circuit_limit": "string",
        "volume": "string",
        "date": "string",
        "time": "string",
        "close": "string",
        "bid_size": "string",
        "ask_size": "string",
        "average_price": "string",
        "exchange_type": "string",
        "lot_size": "string",
        "average_volume": "string",
        "deviation": "string",
        "actual_deviation": "string",
        "no_of_days_for_average": "string",
        "overall_rating": "string",
        "short_term_trends": "string",
        "long_term_trends": "string",
        "year_low": "string",
        "year_high": "string",
        "ric": "string"
      }
      // ... more top gainers
    ],
    "top_losers": [
      {
        // ... same fields as top gainers
      }
      // ... more top losers
    ]
  }
}
```

**Features:**

- **Top Gainers/Losers:** Provides a list of the top 3 gaining stocks and the top 3 losing stocks, ranked by percentage change.
- **Real-time Data:** The data is sourced from a live financial data feed, ensuring you get the latest market information.
- **Comprehensive Stock Information:** Each stock object includes a wide range of data points, including:
  - **Basic Data:** Ticker ID, company name, current price, percentage change, net change.
  - **Intraday Data:** High, low, open, volume.
  - **Previous Close:** Closing price of the previous trading day.
  - **Market Depth:** Bid and ask prices, bid and ask sizes.
  - **Circuit Limits:** Exchange-specific circuit limits.
  - **Year High/Low:** The 52-week high and low prices for the stock.
  - **Reuters Instrument Code (RIC):** For accessing data from Reuters services.
  - **Additional Analysis Fields:** Average price, average volume, deviation, overall rating, short-term trends, and long-term trends.
- **Null Value Handling:** The API removes any `null` values from the response, making it easier for you to parse and use the data.

---

### 5. Fetch 52 Week High Low Data

**Endpoint:** `/fetch_52_week_high_low_data`\
**Method:** GET

**Description:**\
Retrieve data for stocks with the highest and lowest prices in the last 52 weeks from both the BSE and NSE.

Note: Response may return empty list when the market is closed!

**Example Request:**

```
GET /fetch_52_week_high_low_data
```

**Example Response:**

```json
{
    "BSE_52WeekHighLow": {
        "high52Week": [
            {
                "ticker": "RELIANCE.BO",
                "company": "Reliance Industries",
                "price": 2200.55,
                "52_week_high": 2300.00
            },
            ...
        ],
        "low52Week": [
            {
                "ticker": "TATASTEEL.BO",
                "company": "Tata Steel",
                "price": 850.00,
                "52_week_low": 800.00
            },
            ...
        ]
    },
    "NSE_52WeekHighLow": {
        "high52Week": [
            {
                "ticker": "INFY.NS",
                "company": "Infosys",
                "price": 1500.75,
                "52_week_high": 1550.00
            },
            ...
        ],
        "low52Week": [
            {
                "ticker": "HCLTECH.NS",
                "company": "HCL Technologies",
                "price": 1000.00,
                "52_week_low": 950.00
            },
            ...
        ]
    }
}
```

---

### 6. NSE Most Active

**Endpoint:** `/NSE_most_active`\
**Method:** GET

**Description:**\
Get the latest most active stocks in the National Stock Exchange (NSE) based on trading volume.

**Example Request:**

```
GET /NSE_most_active
```

**Example Response:**

```json
[
    {
        "ticker": "RELIANCE.NS",
        "company": "Reliance Industries",
        "price": 2200.55,
        "percent_change": 0.70,
        "net_change": 15.45,
        "volume": 12000000
    },
    ...
]
```

---

### 7. BSE Most Active

**Endpoint:** `/BSE_most_active`\
**Method:** GET

**Description:**\
Get the latest most active stocks in the Bombay Stock Exchange (BSE) based on trading volume.

**Example Request:**

```
GET /BSE_most_active
```

**Example Response:**

```json
[
    {
        "ticker": "TATAMOTORS.BO",
        "company": "Tata Motors",
        "price": 450.75,
        "percent_change": 0.28,
        "net_change": 1.25,
        "volume": 8000000
    },
    ...
]
```

---

### 8. Mutual Funds

**Endpoint:** `/mutual_funds`\
**Method:** GET

**Description:**\
Retrieve the latest data for mutual funds, including net asset value (NAV), returns, and other details.

**Example Request:**

```
GET /mutual_funds
```

**Example Response:**

```json
{
    "Equity": {
        "Large Cap": [
            {
                "fund_name": "SBI Bluechip Fund",
                "latest_nav": 45.67,
                "percentage_change": 0.45,
                "asset_size": 25000,
                "1_month_return": 1.2,
                "3_month_return": 3.5,
                "6_month_return": 5.0,
                "1_year_return": 12.5,
                "3_year_return": 40.2,
                "5_year_return": 70.5,
                "star_rating": 4
            },
            ...
        ]
    },
    ...
}
```

---

### 9. Price Shockers

**Endpoint:** `/price_shockers`\
**Method:** GET

**Description:**\
Get data for stocks that have experienced significant price changes in a short period of time.

**Example Request:**

```
GET /price_shockers
```

**Example Response:**

```json
[
    {
        "ticker": "BPCL.NS",
        "company": "Bharat Petroleum Corporation",
        "price": 309.15,
        "percent_change": -1.27,
        "net_change": -3.98,
        "high": 319,
        "low": 308.7,
        "open": 318,
        "volume": 18726562
    },
    ...
]
```

### 10. Commodity Futures Data API

This API provides access to real-time and historical data for commodity futures contracts traded on an exchange.

### Endpoint: /commodities

**Method:** GET

**Description:**

Retrieves a snapshot of market data for currently active commodity futures contracts. The response includes details on prices, trading volume, open interest, and other relevant metrics.

**Example Response (JSON):**

```json
[
  {
    "contractId": "QIU2O5ABzMxWRO9BIztY",
    "dataTimestamp": "Jun 21 2024 7:46PM",
    "commoditySymbol": "ALUMINIUM",
    "expiryDate": "28 Jun 2024",
    "lastTradedPrice": 230.75,
    "lastTradeQuantity": 1,
    "lastTradeTime": "Jun 21 2024 7:46PM",
    "averageTradedPrice": 231.09,
    "totalVolume": 1369,
    "openInterest": 1066,
    "openingPrice": 232.3,
    "highPrice": 232.85,
    "lowPrice": 230.0,
    "closingPrice": 232.45,
    "totalTradedValue": 158183500000,
    "priceUnit": "KGS",
    "contractSize": 5,
    "contractMonth": "JUN2024",
    "priceChange": -1.6999999999999886,
    "percentageChange": -0.7313400731340024
  },
  {
    // ... more contract objects with the same structure
  }
]
```

**Field Descriptions:**

\| Field \| Description \| \|---\|---\| \| `contractId` \| Unique identifier for the futures contract. \| \| `dataTimestamp` \| Timestamp indicating when this market data snapshot was taken. \| \| `commoditySymbol` \| Standardized symbol representing the traded commodity (e.g., "ALUMINIUM"). \| \| `expiryDate` \| Contract expiration date. \| \| `lastTradedPrice` \| The most recent trade price for this contract. \| \| `lastTradeQuantity` \| Quantity of contracts traded in the last trade. \| \| `lastTradeTime` \| Timestamp of the most recent trade execution. \| \| `averageTradedPrice` \| Average price of trades for the session. \| \| `totalVolume` \| Total contracts traded during the session. \| \| `openInterest` \| Number of active, unsettled contracts. \| \| `openingPrice` \| Price of the first trade of the session. \| \| `highPrice` \| Highest price during the session. \| \| `lowPrice` \| Lowest price during the session. \| \| `closingPrice` \| Price at the end of the session. \| \| `totalTradedValue` \| Total monetary value of trades for the session. \| \| `priceUnit` \| Unit of price quotation (e.g., "KGS", "BBL"). \| \| `contractSize` \| Standard number of commodity units per contract. \| \| `contractMonth` \| Month and year of contract expiration (e.g., "JUN2024"). \| \| `priceChange` \| Difference in closing price from the previous session. \| \| `percentageChange` \| Price change as a percentage of the previous close. \|

---

#### 11. Analyst Recommendations

The `/stock_target_price` endpoint provides clients with target price information, including historical snapshots, and analyst recommendation details for a specified stock.

#### HTTP Request

- **GET** `/stock_target_price?stock_id=&lt;stock_id&gt;`

#### URL Parameters

- **stock_id** (required): The unique identifier of the stock for which target price and recommendation data is being requested.

#### Success Response

The success response contains two major parts: target price details (`priceTarget` and `priceTargetSnapshots`) and analyst recommendations (`recommendation` and `recommendationSnapshots`).

- **Status Code**: `200 OK`
- **Content-Type**: `application/json`
- **Response Body**:

```json
{
  "priceTarget": {
    "CurrencyCode": "INR",
    "UnverifiedMean": 4305.17073171,
    "PreliminaryMean": 4305.17073171,
    ... // Additional price target details
  },
  "priceTargetSnapshots": [
    {
      "CurrencyCode": "INR",
      "Mean": 4305.17073171,
      ... // Additional details for OneWeekAgo
    },
    ... // Other snapshots (ThirtyDaysAgo, SixtyDaysAgo, etc.)
  ],
  "recommendation": {
    "UnverifiedMean": 2.46511628,
    "PreliminaryMean": 2.46511628,
    ... // Additional recommendation details
  },
  "recommendationSnapshots": [
    {
      "Mean": 2.46511628,
      ... // Additional details for OneWeekAgo
    },
    ... // Other snapshots (ThirtyDaysAgo, SixtyDaysAgo, etc.)
  ]
}
```

#### Error Responses

- **Status Code**: `404 Not Found`
  - **Response Body**: `{"error": "Stock target price not found"}`
- **Status Code**: `500 Internal Server Error`
  - **Response Body**: `{"error": "An error occurred: &lt;error_message&gt;"}`

#### Recommendations Key

The `recommendation` field provides an aggregate of analyst recommendations for a specific stock, translating numerical values to qualitative assessments. These recommendations are based on various analyses and forecasts regarding the future performance of the stock relative to the current market expectations. Here's a breakdown of what each numerical value represents:

- **1** - **Buy**: Indicates strong confidence from analysts that the stock will outperform the market in the near future.
- **2** - **Outperform**: Analysts believe the stock will perform better than the average market return.
- **3** - **Hold**: Suggests that analysts view the stock as adequately valued, recommending investors maintain their position without buying more or selling.
- **4** - **Underperform**: Predicts that the stock will fare slightly worse than the market average.
- **5** - **Sell**: Advises that the stock is expected to underperform significantly and may decrease in value, suggesting investors should consider selling it off.

#### Recommendation Snapshots

The recommendation details are not only provided for the current assessment but also include snapshots from previous periods to show how analyst perspectives have evolved over time. Here's the temporal hierarchy of the available snapshots:

- **1 wk ago**: Offers insight into how the recommendations stood one week prior.
- **30 days ago**: Indicates the cumulative recommendations from approximately a month before.
- **60 days ago**: Provides a look back at the analyst sentiment two months ago.
- **90 days ago**: Shows the analyst recommendations from three months prior, giving a quarterly perspective.

These snapshots allow investors to track changes in analyst sentiment over time, potentially indicating trends or shifts in market or company fundamentals affecting the stock.

#### Example Response

```json
{
  "priceTarget": {
    "CurrencyCode": "INR",
    "UnverifiedMean": 4305.17073171,
    "PreliminaryMean": 4305.17073171,
    "Mean": 4305.17073171,
    "High": 4800,
    "Low": 3165,
    "NumberOfEstimates": 41,
    "Median": 4400,
    "StandardDeviation": 354.83960478
  },
  "priceTargetSnapshots": {
    "PriceTargetSnapshot": [
      {
        "CurrencyCode": "INR",
        "Mean": 4305.17073171,
        "High": 4800,
        "Low": 3165,
        "NumberOfEstimates": 41,
        "Median": 4400,
        "StandardDeviation": 354.83960478,
        "Age": "OneWeekAgo"
      },
      {
        "CurrencyCode": "INR",
        "Mean": 4178.83333333,
        "High": 4787,
        "Low": 3040,
        "NumberOfEstimates": 42,
        "Median": 4262.5,
        "StandardDeviation": 405.35392044,
        "Age": "ThirtyDaysAgo"
      },
      {
        "CurrencyCode": "INR",
        "Mean": 4184.66666667,
        "High": 4787,
        "Low": 3040,
        "NumberOfEstimates": 42,
        "Median": 4300,
        "StandardDeviation": 405.9466904,
        "Age": "SixtyDaysAgo"
      },
      {
        "CurrencyCode": "INR",
        "Mean": 4186.4047619,
        "High": 4787,
        "Low": 3040,
        "NumberOfEstimates": 42,
        "Median": 4300,
        "StandardDeviation": 404.71218677,
        "Age": "NinetyDaysAgo"
      }
    ]
  },
  "recommendation": {
    "UnverifiedMean": 2.46511628,
    "PreliminaryMean": 2.46511628,
    "Mean": 2.46511628,
    "High": 1,
    "Low": 5,
    "NumberOfRecommendations": 43,
    "Statistics": {
      "Statistic": [
        {
          "Recommendation": 1,
          "NumberOfAnalysts": 6
        },
        {
          "Recommendation": 2,
          "NumberOfAnalysts": 20
        },
        {
          "Recommendation": 3,
          "NumberOfAnalysts": 10
        },
        {
          "Recommendation": 4,
          "NumberOfAnalysts": 5
        },
        {
          "Recommendation": 5,
          "NumberOfAnalysts": 2
        }
      ]
    }
  },
  "recommendationSnapshots": {
    "RecommendationSnapshot": [
      {
        "Mean": 2.46511628,
        "High": 1,
        "Low": 5,
        "NumberOfRecommendations": 43,
        "Statistics": {
          "Statistic": [
            {
              "Recommendation": 1,
              "NumberOfAnalysts": 6
            },
            {
              "Recommendation": 2,
              "NumberOfAnalysts": 20
            },
            {
              "Recommendation": 3,
              "NumberOfAnalysts": 10
            },
            {
              "Recommendation": 4,
              "NumberOfAnalysts": 5
            },
            {
              "Recommendation": 5,
              "NumberOfAnalysts": 2
            }
          ]
        },
        "Age": "OneWeekAgo"
      },
      {
        "Mean": 2.58139535,
        "High": 1,
        "Low": 5,
        "NumberOfRecommendations": 43,
        "Statistics": {
          "Statistic": [
            {
              "Recommendation": 1,
              "NumberOfAnalysts": 5
            },
            {
              "Recommendation": 2,
              "NumberOfAnalysts": 19
            },
            {
              "Recommendation": 3,
              "NumberOfAnalysts": 10
            },
            {
              "Recommendation": 4,
              "NumberOfAnalysts": 7
            },
            {
              "Recommendation": 5,
              "NumberOfAnalysts": 2
            }
          ]
        },
        "Age": "ThirtyDaysAgo"
      },
      {
        "Mean": 2.58139535,
        "High": 1,
        "Low": 5,
        "NumberOfRecommendations": 43,
        "Statistics": {
          "Statistic": [
            {
              "Recommendation": 1,
              "NumberOfAnalysts": 5
            },
            {
              "Recommendation": 2,
              "NumberOfAnalysts": 19
            },
            {
              "Recommendation": 3,
              "NumberOfAnalysts": 10
            },
            {
              "Recommendation": 4,
              "NumberOfAnalysts": 7
            },
            {
              "Recommendation": 5,
              "NumberOfAnalysts": 2
            }
          ]
        },
        "Age": "SixtyDaysAgo"
      },
      {
        "Mean": 2.58139535,
        "High": 1,
        "Low": 5,
        "NumberOfRecommendations": 43,
        "Statistics": {
          "Statistic": [
            {
              "Recommendation": 1,
              "NumberOfAnalysts": 5
            },
            {
              "Recommendation": 2,
              "NumberOfAnalysts": 19
            },
            {
              "Recommendation": 3,
              "NumberOfAnalysts": 10
            },
            {
              "Recommendation": 4,
              "NumberOfAnalysts": 7
            },
            {
              "Recommendation": 5,
              "NumberOfAnalysts": 2
            }
          ]
        },
        "Age": "NinetyDaysAgo"
      }
    ]
  }
}
```

---

### 12. Stock Forecasts

#### Endpoint: /stock_forecasts

This endpoint retrieves detailed forecast information about a specified stock.

**HTTP Method:** `GET`

**Query Parameters:**

- `stock_id`: string (required) - The unique identifier for the stock.
- `measure_code`: `MeasureCode` (required) - The specific measure code to filter the forecasts.
- `period_type`: `PeriodType` (required) - The type of period for which to retrieve forecasts (Annual or Interim).
- `data_type`: `DataType` (required) - Specifies whether to fetch Actuals or Estimates data.
- `age`: `DataAge` (required) - The age of the data to be retrieved.

**Responses:**

- **200 OK**: Successfully retrieved the forecast data. The response body contains forecast data matching the query parameters.
- **404 Not Found**: No forecasts could be found for the specified `stock_id` or measure code.
- **500 Internal Server Error**: An unexpected error occurred while processing the request.

**Example Request:**

```
GET /stock_forecasts?stock_id=tcs&measure_code=EPS&period_type=Annual&data_type=Actuals&age=ThirtyDaysAgo
```

### Classes and Enums

#### PeriodType

Enum representing the type of period.

- ANNUAL: "Annual"
- INTERIM: "Interim"

#### DataType

Enum representing the type of data.

- ACTUALS: "Actuals"
- ESTIMATES: "Estimates"

#### DataAge

Enum representing the age of the data.

- ONE_WEEK_AGO: "OneWeekAgo"
- THIRTY_DAYS_AGO: "ThirtyDaysAgo"
- SIXTY_DAYS_AGO: "SixtyDaysAgo"
- NINETY_DAYS_AGO: "NinetyDaysAgo"
- CURRENT: "Current"

#### MeasureCode

Enum representing the code for specific measures.

- EPS: "EPS" ( Earnings Per Share )

- CPS: "CPS" ( Cash Flow per Share )

- CPX: "CPX" ( Capital Expenditure )

- DPS: "DPS" ( Dividends Per Share )

- EBI: "EBI" ( EBIT )

- EBT: "EBT" ( EBITDA )

- GPS: "GPS" ( EPS - Fully Reported )

- GRM: "GRM" ( Gross Margin )

- NAV: "NAV" ( Net Asset Value )

- NDT: "NDT" ( Net Debt )

- NET: "NET" ( Net Income )

- PRE: "PRE" ( Pre-tax Profit )

- ROA: "ROA" ( Return on Assets )

- ROE: "ROE" ( Return on Equity )

- SAL: "SAL" ( Revenue )

---

### 13. Historical Data

- **Endpoint**: `/historical_data`

- **Method**: `GET`

- **Query Parameters**:
  - `stock_name` (required): string
  - `period` (optional): string, default is "5yr". other: \[1m, 6m, 1yr, 3yr, 5yr, 10yr, max\]
  - `filter` (optional): string, default is "default". other: \[ price, pe, sm, evebitda, ptb, mcs \]

- **Description**: Fetch historical data for a specific stock.

- **Example Request**:

  ```
  GET /historical_data?symbol=TATAMOTORS&period=1yr&filter=price
  ```

Response:

```
{
    "datasets": [
        {
            "metric": "Price",
            "label": "Price on NSE",
            "values": [
                [
                    "2024-06-27",
                    "3934.15"
                ],
                [
                    "2024-06-28",
                    "3904.15"
                ],
                                // ... more
            ],
            "meta": {
                "is_weekly": false
            }
        },
        {
            "metric": "DMA50",
            "label": "50 DMA",
            "values": [
                [
                    "2024-06-27",
                    "3856.07"
                ],
                [
                    "2024-06-28",
                    "3857.95"
                ],
                                // ... more
            ],
            "meta": {

            }
        },
        {
            "metric": "DMA200",
            "label": "200 DMA",
            "values": [
                [
                    "2024-06-27",
                    "3770.33"
                ],
                [
                    "2024-06-28",
                    "3771.66"
                ],
                                // ... more
            ],
            "meta": {

            }
        },
        {
            "metric": "Volume",
            "label": "Volume",
            "values": [
                [
                    "2024-06-27",
                    4727409,
                    {
                        "delivery": null
                    }
                ],
                [
                    "2024-06-28",
                    3030793,
                    {
                        "delivery": 52
                    }
                ],
                                // ... more
            ],
            "meta": {

            }
        }
    ]
}
```

---

### 14. Historical Stats

- **Endpoint**: `/historical_stats`

- **Method**: `GET`

- **Query Parameters**:
  - `stock_name` (required): string
  - `stats` (required): Enum \[ quarter_results, yoy_results, balancesheet, cashflow, ratios, shareholding_pattern_quarterly, shareholding_pattern_yearly\]

- **Description**: Retrieve historical statistics for a specific stock.

- **Example Request**:

  ```
  GET /historical_stats?stock_name=TATAMOTORS&stats=quarter_results
  ```

- **Example Response:**:

```
{
  "Sales": {
    "Jun 2021": 45411,
    "Sep 2021": 46867,
    "Dec 2021": 48885,
    "Mar 2022": 50591,
    "Jun 2022": 52758,
    "Sep 2022": 55309,
    "Dec 2022": 58229,
    "Mar 2023": 59162,
    "Jun 2023": 59381,
    "Sep 2023": 59692,
    "Dec 2023": 60583,
    "Mar 2024": 61237,
    "Jun 2024": 62613
  },
  "Expenses": {
    "Jun 2021": 32748,
    "Sep 2021": 33751,
    "Dec 2021": 35452,
    "Mar 2022": 36746,
    "Jun 2022": 39342,
    "Sep 2022": 40793,
    "Dec 2022": 42676,
    "Mar 2023": 43388,
    "Jun 2023": 44383,
    "Sep 2023": 43946,
    "Dec 2023": 44195,
    "Mar 2024": 44073,
    "Jun 2024": 45951
  },
  "Operating Profit": {
    "Jun 2021": 12663,
    "Sep 2021": 13116,
    "Dec 2021": 13433,
    "Mar 2022": 13845,
    "Jun 2022": 13416,
    "Sep 2022": 14516,
    "Dec 2022": 15553,
    "Mar 2023": 15774,
    "Jun 2023": 14998,
    "Sep 2023": 15746,
    "Dec 2023": 16388,
    "Mar 2024": 17164,
    "Jun 2024": 16662
  },
  "OPM %": {
    "Jun 2021": 28,
    "Sep 2021": 28,
    "Dec 2021": 27,
    "Mar 2022": 27,
    "Jun 2022": 25,
    "Sep 2022": 26,
    "Dec 2022": 27,
    "Mar 2023": 27,
    "Jun 2023": 25,
    "Sep 2023": 26,
    "Dec 2023": 27,
    "Mar 2024": 28,
    "Jun 2024": 27
  },
  "Other Income": {
    "Jun 2021": 721,
    "Sep 2021": 1111,
    "Dec 2021": 1205,
    "Mar 2022": 981,
    "Jun 2022": 789,
    "Sep 2022": 965,
    "Dec 2022": 520,
    "Mar 2023": 1175,
    "Jun 2023": 1397,
    "Sep 2023": 1006,
    "Dec 2023": -96,
    "Mar 2024": 1157,
    "Jun 2024": 962
  },
  "Interest": {
    "Jun 2021": 146,
    "Sep 2021": 142,
    "Dec 2021": 251,
    "Mar 2022": 245,
    "Jun 2022": 199,
    "Sep 2022": 148,
    "Dec 2022": 160,
    "Mar 2023": 272,
    "Jun 2023": 163,
    "Sep 2023": 159,
    "Dec 2023": 230,
    "Mar 2024": 226,
    "Jun 2024": 173
  },
  "Depreciation": {
    "Jun 2021": 1075,
    "Sep 2021": 1116,
    "Dec 2021": 1196,
    "Mar 2022": 1217,
    "Jun 2022": 1230,
    "Sep 2022": 1237,
    "Dec 2022": 1269,
    "Mar 2023": 1286,
    "Jun 2023": 1243,
    "Sep 2023": 1263,
    "Dec 2023": 1233,
    "Mar 2024": 1246,
    "Jun 2024": 1220
  },
  "Profit before tax": {
    "Jun 2021": 12163,
    "Sep 2021": 12969,
    "Dec 2021": 13191,
    "Mar 2022": 13364,
    "Jun 2022": 12776,
    "Sep 2022": 14096,
    "Dec 2022": 14644,
    "Mar 2023": 15391,
    "Jun 2023": 14989,
    "Sep 2023": 15330,
    "Dec 2023": 14829,
    "Mar 2024": 16849,
    "Jun 2024": 16231
  },
  "Tax %": {
    "Jun 2021": 26,
    "Sep 2021": 26,
    "Dec 2021": 26,
    "Mar 2022": 25,
    "Jun 2022": 25,
    "Sep 2022": 26,
    "Dec 2022": 26,
    "Mar 2023": 26,
    "Jun 2023": 26,
    "Sep 2023": 26,
    "Dec 2023": 25,
    "Mar 2024": 26,
    "Jun 2024": 25
  },
  "Net Profit": {
    "Jun 2021": 9031,
    "Sep 2021": 9653,
    "Dec 2021": 9806,
    "Mar 2022": 9959,
    "Jun 2022": 9519,
    "Sep 2022": 10465,
    "Dec 2022": 10883,
    "Mar 2023": 11436,
    "Jun 2023": 11120,
    "Sep 2023": 11380,
    "Dec 2023": 11097,
    "Mar 2024": 12502,
    "Jun 2024": 12105
  },
  "EPS in Rs": {
    "Jun 2021": 24.35,
    "Sep 2021": 26.02,
    "Dec 2021": 26.41,
    "Mar 2022": 27.13,
    "Jun 2022": 25.9,
    "Sep 2022": 28.51,
    "Dec 2022": 29.64,
    "Mar 2023": 31.13,
    "Jun 2023": 30.26,
    "Sep 2023": 31,
    "Dec 2023": 30.56,
    "Mar 2024": 34.37,
    "Jun 2024": 33.28
  }
}
```

---

Indian API

Indian API is an API Hub that provides access to a wide range of APIs for developers to use in their applications.

[Twitter](https://twitter.com/indianapi_in)[Instagram](https://instagram.com/indianapi.in)

### Company

- [Home](https://indianapi.in/)
- [About Us](https://indianapi.in/legal/about)
- [Documentation](https://indianapi.in/documentation)
- [Contact](https://indianapi.in/contact)

### Services

- [API Hub](https://indianapi.in/hub)
- [Indian Stock Market API](https://indianapi.in/indian-stock-market)

### Legal

- [Privacy Policy](https://indianapi.in/legal/privacy)
- [Terms of Service](https://indianapi.in/legal/terms)
- [Refund Policy](https://indianapi.in/legal/refund)
