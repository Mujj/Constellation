<?php

class FooterTest_PageWidget {
  
  var $test;
  var $widget;
  var $context;
  
  function __construct( $context ) {
  
    $this -> context = $context;
    $this -> test_name = str_replace("Test_PageWidget","",get_class($this));
    
  }
  
  function test() {
    
    //$this -> test = new TestForm_PageWidget( $this -> context, $this -> test_name );
    //$this -> test -> run();
    //$this -> test -> end();
    
    $this -> test = new Test_PageWidget( $this -> context, $this -> test_name, $this );
    $this -> test -> run();
    $this -> test -> end();
    
  }
  
  function getFbShare( $vars ) {
    return urldecode( $vars["fb_share"] );
  }
  
}
?>
