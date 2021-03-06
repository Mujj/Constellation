<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">

<xsl:key name="LISTITEMS" match="LISTITEM" use="@styrogroup_val" />

<xsl:template match="LIST">
  
  <div id="{@name}_wrapper">
    <div id="titlebar">
      
      <xsl:if test="@title != ''">
        <h2><xsl:value-of select="@title" /></h2>
      </xsl:if>
      
      <xsl:if test="@allow_add != 'false'">
      <p>
      <a href="{@url}/detail/0">Add a new <xsl:value-of select="@name" /></a>
      </p>
      </xsl:if>
       
      <xsl:if test="@docount != 'false' and ceiling(@totalResults div @rpp) > 1">
        <xsl:variable name="startrecord"><xsl:value-of select="(@page - 1) * @rpp + 1" /></xsl:variable>
        <xsl:call-template name="MULTI_PAGELOOP">
          <xsl:with-param name="page" select="@page" />
          <xsl:with-param name="rpp" select="@rpp" />
          <xsl:with-param name="ppp" select="@ppp" />
          <xsl:with-param name="totalResults" select="@totalResults" />
          <xsl:with-param name="start" select="(floor((@page - 1) div @ppp) * @ppp) + 1" />
          <xsl:with-param name="repeat" select="ceiling(@totalResults div @rpp)"/>
          <xsl:with-param name="SELECTED" select="@page" />
          <xsl:with-param name="TYPE" select="'STATIC'" />
          <xsl:with-param name="BASEFUNC" select="'nextPage'" />
          <xsl:with-param name="ATTRIBS"></xsl:with-param>
          <xsl:with-param name="BASEURL"><xsl:value-of select="@url" /></xsl:with-param>
          <xsl:with-param name="BASEQS"><xsl:value-of select="@query_string" /></xsl:with-param>
          <xsl:with-param name="SITEMS" select="SORTITEMS" />
          <xsl:with-param name="PAGEVAR" select="'apage'" />
        </xsl:call-template>
        
        <span class="count">Items <xsl:value-of select="$startrecord" /> to <xsl:value-of select="$startrecord + @rpp - 1" /> of <xsl:value-of select="@totalResults" /></span>
      </xsl:if>
    
    </div>
    
    <div id="results">
      <xsl:if test="@type = 'css'">
      <xsl:apply-templates select="self::*" mode="css" />
      </xsl:if>
      <xsl:if test="@type = 'table'">
      <xsl:apply-templates select="self::*" mode="table" />
      </xsl:if>
    </div>
    
  </div>
  
</xsl:template>

<xsl:template match="LIST" mode="table">
  <div id="{@classid}">
  <table border="1">
    <xsl:choose>
      <xsl:when test="count(LISTITEM) = 0">
        <xsl:call-template name="NOTABLE">
          <xsl:with-param name="name" select="@name" />
        </xsl:call-template>
      </xsl:when>
      <xsl:otherwise>
        <xsl:apply-templates select="LISTITEM" mode="table" />
      </xsl:otherwise>
    </xsl:choose>
  </table>
	</div>
  
</xsl:template>

<xsl:template match="LISTITEM" mode="table">
  <xsl:if test="(position() = 1) and (../@header!='false')">
  <tr>
    <xsl:apply-templates select="self::*[1]/@*" mode="table_name" />  
  </tr>
  </xsl:if>
  <tr>
    <xsl:apply-templates select="@*" mode="table_data" />  
  </tr>
</xsl:template>

<xsl:template name="NOTABLE">
  <xsl:param name="name">items</xsl:param>
  <tr>
    <td>No <xsl:value-of select="$name" /> available</td>
  </tr>
</xsl:template>

<xsl:template match="@*" mode="table_name">
    <td>
      <xsl:value-of  select="name()"/>
    </td>
</xsl:template>

<xsl:template match="@*" mode="table_data">  
    <td>
      <xsl:call-template name="split">
        <xsl:with-param name="str" select="."/>
        <xsl:with-param name="pat" select="'|'"/>
      </xsl:call-template>
    </td>
</xsl:template>

<!-- CSS LISTS -->

<xsl:template match="LIST" mode="css">
  <div id="list">
  
  <xsl:choose>
    <xsl:when test="count(LISTITEM) = 0">
      <xsl:call-template name="NOCSS">
          <xsl:with-param name="name" select="@name" />
        </xsl:call-template>
    </xsl:when>
    <xsl:otherwise>
      <xsl:if test="count(GROUPITEM) != 0">
        <xsl:apply-templates select="LISTITEM[@styrogroup_val and generate-id(.)=generate-id(key('LISTITEMS', @styrogroup_val))]" mode="css" />
      </xsl:if>
      <xsl:if test="count(GROUPITEM) = 0">
        <xsl:apply-templates select="LISTITEM" mode="css" />
      </xsl:if>
    </xsl:otherwise>
  </xsl:choose>
    
  </div>
  
</xsl:template>

<xsl:template name="NOCSS">
  <xsl:param name="name">items</xsl:param>
  <div class="listitem listitem_1">
     <span class="entry">
      <span class="column_Entry">
      No <xsl:value-of select="$name" /> available.
      </span>
     </span>
  </div>
  
</xsl:template>

<xsl:template match="LISTITEM" mode="css">
  
  <xsl:if test="(position() = 1) and (../@header!='false')">
  <div class="listitem">
    <xsl:apply-templates select="self::*[1]/@*" mode="css_name" />
  </div>
  </xsl:if>
  
  <xsl:variable name="styrogroup" select="@styrogroup_val" />
  <xsl:if test="(count(../GROUP/GROUPITEM) != 0) and (count(preceding-sibling::LISTITEM[@styrogroup_val = $styrogroup]) = 0)">
    <div class="listitem"><span class="column_Group"><xsl:value-of select="@styrogroup_val" /></span></div>
  </xsl:if>
  
  <div class="listitem listitem_{position() mod 2}">
    <xsl:apply-templates select="@*" mode="css_data" />
  </div>
  
</xsl:template>

<xsl:template match="@*" mode="css_name">
  <xsl:variable name="colname"><xsl:value-of select="name()"/></xsl:variable>
  <xsl:choose>
  <xsl:when test="../../HIDDENITEMS/HIDDENITEM[@value=$colname]/@value = $colname">
  </xsl:when>
  <xsl:otherwise>
    <span class="entry">
      <span class="column_{translate($colname, ' ', '')}">
      <xsl:value-of  select="$colname"/>
      </span>
    </span>
  </xsl:otherwise>
  </xsl:choose>
</xsl:template>

<xsl:template match="@*" mode="css_data">  
  
  <xsl:variable name="colname"><xsl:value-of select="name()"/></xsl:variable>
  <xsl:choose>
  <xsl:when test="../../HIDDENITEMS/HIDDENITEM[@value=$colname]/@value = $colname">
  </xsl:when>
  <xsl:otherwise>
    <span class="entry">
      <span class="column_{translate($colname, ' ', '')}">
        <xsl:call-template name="split">
          <xsl:with-param name="str" select="."/>
          <xsl:with-param name="pat" select="'|'"/>
        </xsl:call-template>
      </span>
    </span>
  </xsl:otherwise>
  </xsl:choose>
</xsl:template>

</xsl:stylesheet>
